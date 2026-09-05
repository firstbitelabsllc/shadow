#!/usr/bin/env python3
"""One local, privately journaled board for this computer.

Entity plans keep milestone/checkpoint text, proof, and evidence under the
private Shadow home. This file stores only project priority, entity-plan
locators and resume checkpoints, and claims. It never becomes a second task
authority or a source-controlled queue.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import copy
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
from typing import Callable, Iterator, NamedTuple

import shadow_git as _shadow_git
import shadow_remote_claim as _remote_claim
from shadow_scrub_lib import PRIVATE_PATH_RE, SECRET_SHAPE_RE
import shadow_plan_grammar as _grammar
import shadow_plan_store as _plan_store


V1_SCHEMA = "shadow.root-board.v1"
SCHEMA = V1_SCHEMA
V2_SCHEMA = "shadow.root-board.v2"
DEFAULT_CLAIM_HOURS = 8
COMPLETION_RESERVATION_MINUTES = 10
RECOVERY_ACTION = "probe-proof-then-adopt-park-or-close"
ROW_ID = _grammar.ROW_ID_RE
ENTITY_ID = re.compile(r"[0-9a-f]{64}")
MILESTONE_PREFIX_RE = re.compile(r"^[A-Za-z]+\d+\s*[—-]\s*")
GIT_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{1,31}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
BOARD_NAME = "board.json"
LOCK_NAME = ".board.lock"
INIT_REGISTRATION_REF_PREFIX = "refs/shadow/init"
MAX_INIT_REGISTRATION_RECEIPT_BYTES = 1024
MAX_PLAN_BYTES = 1_000_000
# Same-identity copies whose state one live-or-retired discovery verdict may
# hold as a predicate. Bounded for the same reason every other import input is:
# a caller cannot make one reconcile stat an unbounded list of locators.
MAX_DISCOVERY_WITNESSES = 256
HOT_PLAN_MAX_BYTES = 256 * 1024
HOT_PLAN_MAX_TASK_ROWS = 128
HOT_PLAN_MAX_MILESTONES = 32
HOT_TASK_ROW_RE = _grammar.HOT_TASK_ROW_RE
GIT_TIMEOUT_SECONDS = 30


class BoardError(ValueError):
    """The local board is unsafe, malformed, or could not be updated."""


class BoardMutation(NamedTuple):
    payload: dict
    changed: bool
    event: dict[str, object] | None


class AlreadyClaimed(BoardError):
    def __init__(self, owner: str):
        super().__init__(f"claimed by {owner}")
        self.owner = owner


class _RepositoryIdentityCache:
    def __init__(self) -> None:
        self.origins: dict[str, str] = {}
        self.plan_parts: dict[str, tuple[str, str]] = {}
        self.repositories: dict[str, Path] = {}
        self.heads: dict[str, str] = {}

    def clear(self) -> None:
        self.origins.clear()
        self.plan_parts.clear()
        self.repositories.clear()
        self.heads.clear()


_REPOSITORY_IDENTITIES: ContextVar[_RepositoryIdentityCache | None] = ContextVar(
    "shadow_repository_identities",
    default=None,
)


@contextmanager
def repository_identity_cache() -> Iterator[None]:
    """Reuse immutable Git identity metadata within one reconciliation pass."""
    token = _REPOSITORY_IDENTITIES.set(_RepositoryIdentityCache())
    try:
        with _remote_claim.upstream_binding_cache():
            yield
    finally:
        _REPOSITORY_IDENTITIES.reset(token)


def _refresh_repository_identity_cache() -> None:
    cache = _REPOSITORY_IDENTITIES.get()
    if cache is not None:
        cache.clear()


def _directory(home: Path | None = None) -> Path:
    return (home or Path.home()).resolve() / ".shadow"


def _safe_root(home: Path | None = None) -> Path:
    """Resolve one private board directory without following a relocated root."""
    root = _directory(home)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise BoardError("root board directory must be a real private directory")
    try:
        if root.resolve(strict=False) != root:
            raise BoardError("root board directory must not cross a symlink")
    except OSError as exc:
        raise BoardError("root board directory is unsafe or unavailable") from exc
    return root


def local_plans_root(home: Path | None = None) -> Path:
    """Return this computer's private, intentionally untracked plan root."""
    return _safe_root(home) / "plans"


def _local_plan_root_containing(plan: Path, home: Path | None = None) -> Path | None:
    """Return the private plan root that owns ``plan``, or None.

    A directory name is not authority. A source repository may legitimately
    carry ``<repo>/.shadow/plans/release/PLAN.md``: that plan is committed and
    public, and must keep its Git identity rather than silently skipping the
    clean/committed checks. So a plan counts as machine-local only when it
    sits under the plan root this computer is configured with, or under a
    ``.shadow/plans`` directory that no enclosing repository tracks.
    """
    candidate = Path(os.path.abspath(plan))
    try:
        root = local_plans_root(home).resolve()
        candidate.resolve().relative_to(root)
        return root
    except (OSError, ValueError, BoardError):
        pass
    for parent in (candidate.parent, *candidate.parents):
        if parent.name != "plans" or parent.parent.name != ".shadow":
            continue
        # Walk from the store's own parent: the private board's Git journal
        # lives inside `.shadow` and must not make its plans look tracked.
        if _git_marker(parent.parent.parent) is not None:
            return None
        return parent
    return None


def is_local_plan(plan: Path, *, home: Path | None = None) -> bool:
    """Whether ``plan`` belongs to the machine-only Shadow plan store."""
    return _local_plan_root_containing(plan, home) is not None


def local_plan_slug(name: str) -> str:
    """One stable, public-safe directory name for a project's local plan."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if len(slug) < 3:
        slug = f"project-{slug or 'work'}"
    return slug[:48]


def local_plan_for_repo(repo: Path, *, home: Path | None = None) -> Path | None:
    """Return the registered local authority that stands in for ``repo``.

    A project whose plan is machine-local has no ``<repo>/PLAN.md``, so the
    repository-shaped verbs (`shadow amp --repo`, `shadow throw --repo`) would
    otherwise refuse work that `shadow status` happily lists. Only a plan this
    computer's board already registers is returned: this resolves an existing
    authority, it never mints one.
    """
    try:
        root = local_plans_root(home)
    except BoardError:
        return None
    registered = {
        entity.get("plan")
        for entity in (snapshot(home=home) or {}).get("entities", [])
    }
    directories = [repo.name, local_plan_slug(repo.name)]
    try:
        identity = origin_of(repo)
    except BoardError:
        identity = ""
    if identity:
        remote_name = origin_repo_name(identity)
        if remote_name:
            directories.extend((remote_name, local_plan_slug(remote_name)))
    for directory in dict.fromkeys(directories):
        candidate = root / directory / "PLAN.md"
        if not regular_plan(candidate):
            continue
        if str(candidate.resolve()) in registered:
            return candidate.resolve()
    return None


def _empty() -> dict:
    return {
        "schema": SCHEMA,
        "revision": 0,
        "projects": [],
        "entities": [],
        "claims": [],
    }


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(root), *args]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
            env=_shadow_git.sanitized_git_env(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(command, 124, "", str(exc))


def _optional_git_value(result: subprocess.CompletedProcess[str]) -> str | None:
    if result.returncode == 1 and not result.stdout and not result.stderr:
        return None
    if result.returncode:
        raise BoardError("project Git identity could not be read; retry when Git is available")
    values = result.stdout.splitlines()
    if len(values) != 1 or not values[0].strip():
        raise BoardError("project Git identity could not be read; retry when Git is available")
    return values[0].strip()


def _git_bytes(
    root: Path,
    *args: str,
    content: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    command = ["git", "-C", str(root), *args]
    try:
        return subprocess.run(
            command,
            input=content,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
            env=_shadow_git.sanitized_git_env(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(command, 124, b"", str(exc).encode())


def _git_marker(path: Path) -> Path | None:
    cursor = Path(os.path.abspath(path))
    while cursor.parent != cursor:
        marker = cursor / ".git"
        if marker.exists() or marker.is_symlink():
            return marker
        cursor = cursor.parent
    return None


def well_formed_proof_origin(value: str) -> str:
    """A plan-owned proof origin is one already-normalized public Git identity."""
    if not value or any(char.isspace() for char in value):
        raise ValueError("not a normalized Git identity")
    if value.startswith(("/", "~", ".", "local-remote:")) or "\\" in value or ".." in value:
        raise ValueError("not a normalized Git identity")
    if PRIVATE_PATH_RE.search(value):
        raise ValueError("not a normalized Git identity")
    identity = normalized_origin(value)
    host, sep, path = identity.partition("/")
    if (
        identity != value
        or not sep
        or not path
        or "." not in host.split(":", 1)[0]
    ):
        raise ValueError("not a normalized Git identity")
    return identity


def normalized_origin(origin: str) -> str:
    return _shadow_git.normalized_origin(origin)




def regular_plan(plan: Path) -> bool:
    """A live authority is one canonical regular PLAN.md with no symlink component."""
    candidate = Path(os.path.abspath(plan))
    try:
        if candidate.name != "PLAN.md" or not candidate.is_file() or candidate.is_symlink():
            return False
        cursor = candidate.parent
        while cursor.parent != cursor:
            # Filesystem-root aliases (macOS /var and /tmp) are outside a
            # project boundary; canonical storage normalizes them later.
            if cursor.parent.parent == cursor.parent:
                break
            if cursor.is_symlink():
                return False
            marker = cursor / ".git"
            if marker.exists() or marker.is_symlink():
                return not marker.is_symlink()
            cursor = cursor.parent
        return True
    except OSError:
        return False


def plan_state_snapshot(plan: Path) -> tuple[str, bytes | None]:
    """Freeze one locator state and at most the bounded byte prefix it exposes."""
    def unavailable_token() -> str:
        try:
            metadata = os.lstat(plan)
            target = os.readlink(plan) if stat.S_ISLNK(metadata.st_mode) else ""
        except OSError:
            return "unavailable"
        unavailable = (
            f"{metadata.st_mode}\0{metadata.st_size}\0{metadata.st_mtime_ns}\0"
            f"{metadata.st_ctime_ns}\0{metadata.st_dev}\0{metadata.st_ino}\0{target}"
        ).encode("utf-8")
        return hashlib.sha256(unavailable).hexdigest()

    if not regular_plan(plan):
        return unavailable_token(), None
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = -1
    try:
        descriptor = os.open(plan, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            os.close(descriptor)
            descriptor = -1
            return unavailable_token(), None
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            root_content = stream.read(MAX_PLAN_BYTES + 1)
            after = os.fstat(stream.fileno())
    except (OSError, ValueError):
        if descriptor >= 0:
            os.close(descriptor)
        return unavailable_token(), None
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
        return "unavailable", None
    try:
        snapshot = open_plan(plan)
        if snapshot.root_bytes != root_content:
            return "unavailable", None
        content = bounded_plan_content(snapshot)
    except (BoardError, _plan_store.PlanStoreError):
        return unavailable_token(), None
    try:
        final = os.stat(plan, follow_symlinks=False)
    except OSError:
        return "unavailable", None
    final_state = (
        final.st_mode,
        final.st_size,
        final.st_mtime_ns,
        final.st_ctime_ns,
        final.st_dev,
        final.st_ino,
    )
    if final_state != after_state:
        return "unavailable", None
    frozen = (
        "\0".join(str(value) for value in final_state).encode("ascii")
        + b"\0"
        + root_content
    )
    return hashlib.sha256(frozen).hexdigest(), content


def bounded_plan_content(snapshot: _plan_store.PlanSnapshot) -> bytes:
    """Materialize one snapshot only while its own declared size stays bounded.

    Codex (PR #469, P1): a partitioned plan declares its logical size in the
    root, and the tree format's structural capacity is far larger than the bound
    every reader shares. Refusing on `logical_bytes` before traversal keeps board
    discovery and browser scanning from allocating an oversized plan, and the
    length recheck keeps the bound true for the bytes actually produced.
    """
    declared = (
        snapshot.root["logical_bytes"] if snapshot.is_tree else len(snapshot.root_bytes)
    )
    if declared > MAX_PLAN_BYTES:
        raise BoardError("plan exceeds the bounded size limit")
    try:
        content = snapshot.materialize()
    except _plan_store.PlanStoreError as exc:
        raise BoardError(str(exc)) from exc
    if len(content) > MAX_PLAN_BYTES:
        raise BoardError("plan exceeds the bounded size limit")
    return content


def read_plan_bytes(plan: Path) -> bytes:
    """Read one bounded logical plan through the shared storage owner."""
    return bounded_plan_content(open_plan(plan))


def open_plan(plan: Path) -> _plan_store.PlanSnapshot:
    """Open one legacy or partitioned authority through its canonical owner."""
    if not regular_plan(plan):
        raise BoardError("plan must be a regular non-symlink PLAN.md")
    try:
        return _plan_store.PlanSnapshot.open(plan)
    except _plan_store.PlanStoreError as exc:
        raise BoardError(str(exc)) from exc


def read_plan_text(plan: Path) -> str:
    """Decode the one bounded PLAN.md authority snapshot shared by all views."""
    try:
        return read_plan_bytes(plan).decode("utf-8")
    except UnicodeError as exc:
        raise BoardError("plan is not valid UTF-8") from exc


def hot_plan_budget(content: bytes) -> dict:
    """Measure the checked-in hot-authority limits shared by every entry door."""
    try:
        text = content.decode("utf-8")
    except UnicodeError as exc:
        raise BoardError("plan is not valid UTF-8") from exc
    task_rows = 0
    milestone_count = 0
    in_tasks = False
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            in_tasks = heading == "Tasks" or heading.startswith("Tasks ")
            continue
        if not in_tasks:
            continue
        if line.startswith("### "):
            milestone_count += 1
        if HOT_TASK_ROW_RE.fullmatch(line):
            task_rows += 1
    values = {
        "bytes": len(content),
        "task_rows": task_rows,
        "milestones": milestone_count,
    }
    limits = {
        "bytes": HOT_PLAN_MAX_BYTES,
        "task_rows": HOT_PLAN_MAX_TASK_ROWS,
        "milestones": HOT_PLAN_MAX_MILESTONES,
    }
    exceeded = [name for name, value in values.items() if value > limits[name]]
    return {
        **values,
        "limits": limits,
        "exceeded": exceeded,
        "within_limits": not exceeded,
    }


def _milestones_held_only_by_person_gates(text: str) -> bool:
    """True when every open milestone is held open solely by ``gate`` rows.

    Archive needs a fully completed milestone. When each open milestone is
    kept open by a person-gated row, that remedy does not exist. The budget
    gate must name this shape instead of telling the operator to archive.
    """
    in_tasks = False
    open_rows: list[str] = []
    open_milestones = 0
    person_held = 0

    def close_milestone() -> None:
        nonlocal open_milestones, person_held
        if not open_rows:
            return
        open_milestones += 1
        if all(proof.startswith("gate ") for proof in open_rows):
            person_held += 1

    for line in text.splitlines():
        if line.startswith("## "):
            if in_tasks:
                close_milestone()
            heading = line[3:].strip()
            in_tasks = heading == "Tasks" or heading.startswith("Tasks ")
            open_rows = []
            continue
        if not in_tasks:
            continue
        if line.startswith("### "):
            close_milestone()
            open_rows = []
            continue
        match = _grammar.ROW_RE.fullmatch(line)
        if match is None or match.group("state") == "completed":
            continue
        fields = {
            key: value.strip()
            for key, value in _grammar.FIELD_RE.findall(match.group("tail") or "")
        }
        open_rows.append(fields.get("proof", ""))
    if in_tasks:
        close_milestone()
    return open_milestones >= 1 and open_milestones == person_held


def _has_archive_eligible_milestone(text: str) -> bool:
    """Whether lifecycle can archive at least one milestone from this frozen text."""
    import importlib.util
    import sys

    name = "shadow_lifecycle"
    module = sys.modules.get(name)
    if module is None:
        path = Path(__file__).resolve().parent / "shadow-lifecycle.py"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return False
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    lines = text.splitlines(keepends=True)
    for item in module.milestones(lines):
        try:
            module.validate_milestone(item, lines)
        except module.LifecycleError:
            continue
        return True
    return False


def hot_plan_budget_remedy(content: bytes) -> str:
    """Name the remedy that can actually shrink this hot plan."""
    try:
        text = content.decode("utf-8")
    except UnicodeError:
        return "no archive-eligible milestone; trim or relocate plan text (migration is lossless and does not shrink it)"
    if _has_archive_eligible_milestone(text):
        return "archive one proven milestone with shadow lifecycle"
    if _milestones_held_only_by_person_gates(text):
        return (
            "every open milestone is held only by a person-gated row; "
            "archive cannot run; trim or relocate plan text "
            "(migration is lossless and does not shrink it)"
        )
    return "no archive-eligible milestone; trim or relocate plan text (migration is lossless and does not shrink it)"


def assert_hot_plan_budget(content: bytes) -> dict:
    """Refuse a plan that cannot enter or mutate the normal computer board."""
    measured = hot_plan_budget(content)
    if measured["exceeded"]:
        raise BoardError(
            "hot plan exceeds the checked-in "
            + ", ".join(measured["exceeded"])
            + " budget; "
            + hot_plan_budget_remedy(content)
        )
    return measured


def plan_content_token(text: str) -> tuple[int, str]:
    """Return the byte-size and digest used to CAS a parsed plan into the board."""
    content = text.encode("utf-8")
    return len(content), hashlib.sha256(content).hexdigest()


def plan_state_token(plan: Path) -> str:
    """Fingerprint a locator's bounded state, including an unavailable sentinel."""
    state, _ = plan_state_snapshot(plan)
    return state


def validate_owner(owner: object) -> str:
    """Return one public-safe seat name or refuse it before persistence."""
    if (
        not isinstance(owner, str)
        or not owner
        or owner != owner.strip()
        or not owner.isprintable()
        or len(owner) > 40
        or CONTROL.search(owner)
        or PRIVATE_PATH_RE.search(owner)
        or SECRET_SHAPE_RE.search(owner)
    ):
        raise BoardError(
            "claim owner must be 1-40 public-safe visible characters"
        )
    return owner


def _unreadable_identity(reason: str | None) -> str:
    """One refusal that carries the measured cause, not a guess about Git."""
    if not reason:
        return "project Git identity could not be read; retry when Git is available"
    return f"project Git identity could not be read: {reason}"


def origin_of(repo: Path) -> str:
    repo = Path(os.path.abspath(repo)).resolve()
    cache = _REPOSITORY_IDENTITIES.get()
    cache_key = str(repo)
    if cache is not None and cache_key in cache.origins:
        return cache.origins[cache_key]
    marker = _git_marker(repo)
    if marker is None:
        origin = str(repo)
        if cache is not None:
            cache.origins[cache_key] = origin
        return origin
    binding = _remote_claim.upstream_binding(
        repo,
        recover_detached=True,
    )
    if binding.eligibility is _remote_claim.RemoteEligibility.UNKNOWN:
        # Name the fault the probe measured. "Retry when Git is available"
        # is a claim about Git and credentials this call never tested, and on
        # 2026-09-03 it sent a whole-portfolio refusal after an endpoint the
        # checkout could not pin while `ls-remote` answered in a second.
        raise BoardError(_unreadable_identity(binding.reason))
    origin = binding.public_identity
    if origin is None:
        try:
            fallback = _remote_claim.remote_endpoint(
                repo,
                "origin",
                missing_ok=True,
            )
        except _remote_claim.RemoteClaimError as exc:
            raise BoardError(
                "project Git identity could not be read; retry when Git is available"
            ) from exc
        origin = fallback[1] if fallback is not None else None
    if origin:
        if cache is not None:
            cache.origins[cache_key] = origin
        return origin
    # Linked worktrees share one common Git directory even when the repository
    # has no remote.  The checkout path does not: using it let two worktrees of
    # one local repository both claim the same logical row.
    common = _optional_git_value(
        _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    )
    if common is None:
        raise BoardError("project Git identity could not be read; retry when Git is available")
    origin = _shadow_git.local_git_identity(repo, common)
    if cache is not None:
        cache.origins[cache_key] = origin
    return origin


def origin_repo_name(origin: str) -> str:
    tail = origin.rstrip("/").removesuffix(".git")
    return tail.rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def public_entity_locator(identity: object) -> str:
    """Name one logical entity without deriving display data from its private pointer."""
    if not isinstance(identity, str) or not ENTITY_ID.fullmatch(identity):
        raise BoardError("public entity locator requires one logical entity id")
    return f"entity@{identity[:12]}/PLAN.md"


def public_copy_locator(identity: object, display: object) -> str:
    """Name one discovered checkout without emitting its machine-owned path."""
    if not isinstance(identity, str) or not ENTITY_ID.fullmatch(identity):
        raise BoardError("public copy locator requires one logical entity id")
    if not isinstance(display, str) or not display:
        raise BoardError("public copy locator requires one discovered plan label")
    digest = hashlib.sha256(f"{identity}\0{display}".encode("utf-8")).hexdigest()[:12]
    return f"copy@{digest}/PLAN.md"


def public_discovery_locator(identity: object, display: object) -> str:
    """Keep useful relative labels public; make unsafe discovery labels opaque."""
    if not isinstance(display, str) or not display:
        raise BoardError("public discovery locator requires one discovered plan label")
    path = Path(display)
    unsafe = (
        len(display) > 240
        or not display.isprintable()
        or bool(CONTROL.search(display))
        or bool(PRIVATE_PATH_RE.search(display))
        or bool(SECRET_SHAPE_RE.search(display))
        or path.is_absolute()
        or ".." in path.parts
    )
    return public_copy_locator(identity, display) if unsafe else display


def public_plan_locator(plan: Path) -> str:
    """Return a stable human locator without exposing an absolute home path.

    The repo resolution rides the same per-pass identity cache as
    plan_identity_parts; status used to pay one toplevel probe per entity.
    Unlike plan_identity_parts this locator never raises: an unreadable
    probe falls back to the display form below.
    """
    candidate = Path(os.path.abspath(plan))
    cache = _REPOSITORY_IDENTITIES.get()
    marker = _git_marker(candidate.parent)
    marker_key = str(Path(os.path.abspath(marker))) if marker is not None else None
    repo = (
        cache.repositories.get(marker_key)
        if cache is not None and marker_key is not None
        else None
    )
    if repo is None:
        result = _git(candidate.parent, "rev-parse", "--show-toplevel")
        if result.returncode or not result.stdout.strip():
            public = f"{candidate.parent.name}/PLAN.md"
            if SECRET_SHAPE_RE.search(public) or PRIVATE_PATH_RE.search(public):
                digest = hashlib.sha256(public.encode("utf-8")).hexdigest()[:8]
                return f"entity@{digest}/PLAN.md"
            return public
        repo = Path(result.stdout.strip()).resolve()
        if cache is not None and marker_key is not None:
            cache.repositories[marker_key] = repo
    try:
        relative = candidate.relative_to(repo).as_posix()
    except ValueError:
        relative = candidate.name
    try:
        origin = origin_of(repo)
    except BoardError:
        # The contract above is never-raises: a transient identity read
        # degrades to the local digest shape, never a crashed render.
        origin = str(repo)
    if origin.startswith("local-") or origin.startswith("/"):
        digest = hashlib.sha256(origin.encode("utf-8")).hexdigest()[:8]
        prefix = f"{repo.name}@{digest}"
    else:
        prefix = origin
    public = f"{prefix}/{relative}"
    if SECRET_SHAPE_RE.search(public) or PRIVATE_PATH_RE.search(public):
        digest = hashlib.sha256(public.encode("utf-8")).hexdigest()[:8]
        return f"entity@{digest}/PLAN.md"
    return public


def plan_commit_time(plan: Path) -> int | None:
    """Commit time of the last commit that touched this exact plan file.

    Filesystem mtime cannot order two copies of one logical plan: a checkout,
    a `git worktree add`, or a `disk-clean` sweep restamps a file without
    changing a word of it. Commit time is the only ordering that survives
    those, so it is what decides which copy is speaking for the identity now.

    `None` means "no opinion", never "old": a file outside a repository, an
    untracked plan, a partial clone missing the commit, or a git failure all
    land here so callers can fall back to current behaviour instead of
    treating an unreadable copy as the oldest one.
    """
    plan = Path(os.path.abspath(plan))
    result = _git(plan.parent, "log", "-1", "--format=%ct", "--", str(plan))
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    try:
        return int(raw)
    except ValueError:
        return None


def plan_commit_times(repo: Path, plans: list[Path]) -> dict[str, int | None]:
    """Latest touching commit time for many plans, in one git process.

    Same semantics as plan_commit_time per path: the newest commit touching
    each exact pathspec, or no opinion when nothing touches it. One
    `git log --name-only` answers the whole set — per-plan `git log -1` was
    the entire subprocess cost of a several-hundred-plan reconcile.
    """
    relative_to_abs: dict[str, str] = {}
    relpaths: list[str] = []
    for plan in plans:
        absolute = Path(os.path.abspath(plan))
        try:
            relative = absolute.relative_to(repo).as_posix()
        except ValueError:
            continue
        relative_to_abs[relative] = str(absolute)
        relpaths.append(relative)
    if not relpaths:
        return {}
    result = _git(
        repo,
        "log",
        "--format=COMMIT%x09%ct",
        "--name-only",
        "--",
        *relpaths,
    )
    if result.returncode:
        return {}
    times: dict[str, int | None] = {}
    current: int | None = None
    for line in result.stdout.splitlines():
        if line.startswith("COMMIT\t"):
            raw = line.split("\t", 1)[1]
            try:
                current = int(raw)
            except ValueError:
                current = None
            continue
        path = line.strip()
        if path and path in relative_to_abs and relative_to_abs[path] not in times:
            times[relative_to_abs[path]] = current
    return times


def plan_identity_parts(plan: Path, *, require_regular: bool = False) -> tuple[str, str]:
    """Resolve logical identity fields without reading the PLAN.md body."""
    if require_regular and not regular_plan(plan):
        raise BoardError("entity identity requires a regular, non-symlink PLAN.md")
    plan = Path(os.path.abspath(plan))
    cache = _REPOSITORY_IDENTITIES.get()
    cache_key = str(plan)
    if cache is not None and cache_key in cache.plan_parts:
        return cache.plan_parts[cache_key]
    local_root = _local_plan_root_containing(plan)
    if local_root is not None:
        try:
            parts = (
                f"local-plan:{local_root}",
                plan.resolve().relative_to(local_root).as_posix(),
            )
        except (OSError, ValueError) as exc:
            raise BoardError("local plan identity could not be read") from exc
        if cache is not None:
            cache.plan_parts[cache_key] = parts
        return parts
    marker = _git_marker(plan.parent)
    marker_key = str(Path(os.path.abspath(marker))) if marker is not None else None
    repo = cache.repositories.get(marker_key) if cache is not None and marker_key else None
    git_repository = repo is not None
    if repo is None:
        result = _git(plan.parent, "rev-parse", "--show-toplevel")
        if result.returncode == 0 and result.stdout.strip():
            repo = Path(result.stdout.strip()).resolve()
            git_repository = True
            if cache is not None and marker_key is not None:
                cache.repositories[marker_key] = repo
        elif marker is not None:
            # `git -C` on a directory that does not exist fails the same way a
            # broken Git does. Recorded 2026-08-12 and measured again
            # 2026-09-03: the fault is a registered pointer into a path this
            # checkout does not carry — absent from HEAD, or on another branch.
            raise BoardError(
                _unreadable_identity(
                    None
                    if plan.parent.is_dir()
                    else "the plan pointer's directory is absent from this checkout"
                )
            )
        else:
            repo = plan.parent
    if git_repository:
        try:
            relative = plan.relative_to(repo).as_posix()
        except ValueError:
            try:
                relative = (plan.parent.resolve() / plan.name).relative_to(repo).as_posix()
            except ValueError:
                relative = plan.name
    else:
        relative = plan.name
    parts = origin_of(repo), relative
    if cache is not None:
        cache.plan_parts[cache_key] = parts
    return parts


def entity_id(plan: Path) -> str:
    """Logical entity identity: normalized origin plus repository-relative path."""
    return logical_entity_id(*plan_identity_parts(plan, require_regular=True))


def logical_entity_id(origin: str, relative: str) -> str:
    """Hash the logical identity already resolved by bounded discovery."""
    logical = f"{origin}\0{relative}".encode("utf-8")
    return hashlib.sha256(logical).hexdigest()


def head_plan_snapshot(
    plan: Path,
    *,
    repo: Path | None = None,
) -> tuple[dict[str, str], bytes]:
    """Return the exact PLAN bytes stored at HEAD, independent of worktree dirt.

    A caller that already authenticated the repo (e.g. status, via the
    upstream binding) passes it in and skips the redundant resolution; the
    plan-in-repo containment check and the post-read HEAD race-guard stay.
    """
    if not regular_plan(plan):
        raise BoardError("entity plan must be a regular, non-symlink PLAN.md")
    plan = plan.resolve()
    if repo is not None:
        repo = repo.resolve()
    cache = _REPOSITORY_IDENTITIES.get()
    if repo is None:
        top = _git(plan.parent, "rev-parse", "--show-toplevel")
        if top.returncode or not top.stdout.strip():
            raise BoardError("entity plan must be committed in a Git repository")
        repo = Path(top.stdout.strip()).resolve()
    try:
        relative = plan.relative_to(repo).as_posix()
    except ValueError as exc:
        raise BoardError("entity plan is outside its Git repository") from exc
    repo_key = str(repo)
    if cache is not None and repo_key in cache.heads:
        head = subprocess.CompletedProcess(
            ["git"], 0, cache.heads[repo_key] + "\n", ""
        )
    else:
        head = _git(repo, "rev-parse", "HEAD")
        if not head.returncode and cache is not None:
            cache.heads[repo_key] = head.stdout.strip()
    blob = _git(repo, "rev-parse", f"HEAD:{relative}")
    if head.returncode or blob.returncode:
        raise BoardError("entity plan is not present at the current Git HEAD")
    frozen = _git_bytes(repo, "cat-file", "blob", blob.stdout.strip())
    if frozen.returncode:
        raise BoardError("entity plan HEAD bytes could not be frozen")
    head_after = _git(repo, "rev-parse", "HEAD")
    if head_after.returncode or head_after.stdout.strip() != head.stdout.strip():
        raise BoardError("entity plan ref changed while it was being read; retry")
    return (
        {
            "repo": str(repo),
            "relative": relative,
            "head": head.stdout.strip(),
            "blob": blob.stdout.strip(),
        },
        frozen.stdout,
    )


def committed_plan_snapshot(
    plan: Path,
    *,
    repo: Path | None = None,
) -> tuple[dict[str, str], bytes]:
    """Return worktree bytes and the exact Git object that serves them, or refuse."""
    token, _ = head_plan_snapshot(plan, repo=repo)
    repo = Path(token["repo"])
    relative = token["relative"]
    snapshot = open_plan(plan)
    tracked_paths = [relative]
    if snapshot.is_tree:
        tracked_paths.append(
            (Path(relative).parent / "PLAN.d").as_posix()
        )
    status = _git(repo, "status", "--porcelain=v1", "--", *tracked_paths)
    if status.returncode:
        raise BoardError("entity plan Git state could not be read")
    if status.stdout.strip():
        raise BoardError("entity plan or its staged index changed; commit or restore it first")
    try:
        root_content = plan.read_bytes()
    except OSError as exc:
        raise BoardError("entity plan bytes could not be frozen") from exc
    hashed = _git_bytes(repo, "hash-object", "--stdin", content=root_content)
    if hashed.returncode or hashed.stdout.decode("ascii", errors="ignore").strip() != token["blob"]:
        raise BoardError("entity plan changed or is uncommitted; retry from one committed ref")
    head_after = _git(repo, "rev-parse", "HEAD")
    if head_after.returncode or head_after.stdout.strip() != token["head"]:
        raise BoardError("entity plan ref changed while it was being read; retry")
    try:
        content = snapshot.materialize()
    except _plan_store.PlanStoreError as exc:
        raise BoardError(str(exc)) from exc
    return token, content


def frozen_plan_snapshot(
    plan: Path,
    *,
    home: Path | None = None,
    repo: Path | None = None,
) -> tuple[dict[str, str], bytes]:
    """Freeze either a product's committed plan or one local-only plan.

    Product repositories remain free to keep a release plan with their source.
    Shadow, ``ai``, and ``ai-leo`` operational plans are deliberately different:
    their authority lives below ``~/.shadow/plans`` and is never committed.
    """
    if not is_local_plan(plan, home=home):
        return committed_plan_snapshot(plan, repo=repo)
    content = read_plan_bytes(plan)
    digest = hashlib.sha256(content).hexdigest()
    return (
        {
            "repo": str(plan.parent.resolve()),
            "relative": plan.name,
            "head": f"local:{digest}",
            "blob": digest,
        },
        content,
    )


@contextmanager
def project_lock(plan: Path) -> Iterator[None]:
    """Serialize one entity plan's local lifecycle across every public verb."""
    if not regular_plan(plan):
        raise BoardError("project lifecycle lock requires a regular, non-symlink PLAN.md")
    if is_local_plan(plan):
        common_dir = plan.parent
    else:
        common = _git(plan.parent, "rev-parse", "--git-common-dir")
        if common.returncode or not common.stdout.strip():
            raise BoardError("project Git common directory could not be resolved")
        common_dir = Path(common.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = (plan.parent / common_dir).resolve()
        if common_dir.is_symlink() or not common_dir.is_dir():
            raise BoardError("project Git common directory is unsafe")
    lock = common_dir / f".shadow-lifecycle-{entity_id(plan)}.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock, flags, 0o600)
    except OSError as exc:
        raise BoardError("project lifecycle lock is unsafe or unavailable") from exc
    with os.fdopen(descriptor, "a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _validate_v1(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "revision", "projects", "entities", "claims"
    }:
        raise BoardError("board has unknown or missing top-level fields")
    if payload["schema"] != V1_SCHEMA:
        raise BoardError("board schema is not supported")
    if isinstance(payload["revision"], bool) or not isinstance(payload["revision"], int):
        raise BoardError("board revision must be an integer")
    if payload["revision"] < 0:
        raise BoardError("board revision cannot be negative")
    if (
        not isinstance(payload["projects"], list)
        or not isinstance(payload["entities"], list)
        or not isinstance(payload["claims"], list)
    ):
        raise BoardError("board projects, entities, and claims must be lists")

    projects: set[str] = set()
    for project in payload["projects"]:
        if not isinstance(project, dict) or set(project) != {"id", "priority"}:
            raise BoardError("projects have unknown or missing fields")
        if not isinstance(project["id"], str) or PROJECT_ID.fullmatch(project["id"]) is None:
            raise BoardError("project id must be a lowercase project slug")
        if project["id"] in projects:
            raise BoardError("a project is listed more than once")
        projects.add(project["id"])
        if isinstance(project["priority"], bool) or project["priority"] not in range(1, 6):
            raise BoardError("project priority must be 1-5")

    plans: set[str] = set()
    entities: set[str] = set()
    for entity in payload["entities"]:
        if not isinstance(entity, dict) or set(entity) != {
            "id", "project", "plan", "resume"
        }:
            raise BoardError("entity pointers have unknown or missing fields")
        if not isinstance(entity["id"], str) or ENTITY_ID.fullmatch(entity["id"]) is None:
            raise BoardError("entity id must be one logical plan hash")
        if entity["id"] in entities:
            raise BoardError("a logical entity is listed more than once")
        entities.add(entity["id"])
        if not isinstance(entity["project"], str) or entity["project"] not in projects:
            raise BoardError("entity points outside the registered projects")
        if (
            not isinstance(entity["plan"], str)
            or CONTROL.search(entity["plan"])
            or not Path(entity["plan"]).is_absolute()
        ):
            raise BoardError("entity plan pointers must be absolute paths")
        if Path(entity["plan"]).name != "PLAN.md":
            raise BoardError("entity pointers must name PLAN.md")
        if entity["plan"] in plans:
            raise BoardError("an entity plan is listed more than once")
        plans.add(entity["plan"])
        if entity["resume"] is not None and (
            not isinstance(entity["resume"], str)
            or ROW_ID.fullmatch(entity["resume"]) is None
        ):
            raise BoardError("entity resume must be one row id or null")

    targets: set[tuple[str, str]] = set()
    for claim in payload["claims"]:
        if not isinstance(claim, dict) or set(claim) != {
            "entity", "row", "owner", "claimed_at", "return_by", "recovery"
        }:
            raise BoardError("claims have unknown or missing fields")
        if not isinstance(claim["entity"], str) or claim["entity"] not in entities:
            raise BoardError("claim points outside the registered entities")
        if not isinstance(claim["row"], str) or ROW_ID.fullmatch(claim["row"]) is None:
            raise BoardError("claim row must be one row id")
        target = (claim["entity"], claim["row"])
        if target in targets:
            raise BoardError("a row has more than one claim")
        targets.add(target)
        validate_owner(claim["owner"])
        claimed_at = _timestamp(claim.get("claimed_at"), "claim time")
        return_by = _timestamp(claim.get("return_by"), "claim return-by")
        if return_by <= claimed_at:
            raise BoardError("claim return-by must be later than its claim time")
        if claim["recovery"] != RECOVERY_ACTION:
            raise BoardError("claim recovery action is not supported")
    return payload


def _validate_write_scope(value: object) -> list[str]:
    if not isinstance(value, list) or len(value) > 256:
        raise BoardError("claim write scope must be a bounded list")
    for prefix in value:
        try:
            encoded_length = len(prefix.encode("utf-8")) if isinstance(prefix, str) else 0
        except UnicodeError as exc:
            raise BoardError("claim write scope must be valid UTF-8") from exc
        if (
            not isinstance(prefix, str)
            or not prefix
            or encoded_length > 1024
            or CONTROL.search(prefix)
            or "\\" in prefix
            or any(character in prefix for character in "*?[]")
            or prefix.startswith("/")
        ):
            raise BoardError("claim write scope contains a noncanonical path")
        components = prefix.split("/")
        if prefix != "." and (
            any(component in {"", ".", ".."} for component in components)
            or ".git" in components
        ):
            raise BoardError("claim write scope contains a noncanonical path")
    if value != sorted(set(value)):
        raise BoardError("claim write scope must be sorted and unique")
    return value


def _validate_repository_binding(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {
        "common_dir_sha256", "remote_identity"
    }:
        raise BoardError("claim repository binding has unknown or missing fields")
    digest = value["common_dir_sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise BoardError("claim repository binding digest must be lowercase SHA-256")
    identity = value["remote_identity"]
    if identity is not None:
        if (
            not isinstance(identity, str)
            or "?" in identity
            or "#" in identity
            or SECRET_SHAPE_RE.search(identity)
            or PRIVATE_PATH_RE.search(identity)
        ):
            raise BoardError("claim remote identity is not a normalized Git identity")
        try:
            well_formed_proof_origin(identity)
        except ValueError as exc:
            raise BoardError(
                "claim remote identity is not a normalized Git identity"
            ) from exc
    return value


def repository_binding(repo: Path, *, remote: str | None = None) -> dict:
    """Bind a checkout using Git's existing endpoint owner, without network I/O."""
    repo = Path(repo).resolve()
    top = _optional_git_value(_git(repo, "rev-parse", "--show-toplevel"))
    common = _optional_git_value(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if top is None or common is None or Path(top).resolve() != repo:
        raise BoardError("repository binding requires one Git worktree root")
    selected = remote
    if selected is None:
        branch = _optional_git_value(_git(repo, "symbolic-ref", "--quiet", "--short", "HEAD"))
        if branch is not None:
            selected = _optional_git_value(_git(repo, "config", "--get-all", f"branch.{branch}.remote"))
    remotes = _git(repo, "remote")
    if remotes.returncode:
        raise BoardError("repository remotes could not be established")
    names = remotes.stdout.splitlines()
    if selected is None:
        if "origin" in names:
            selected = "origin"
        elif names:
            raise BoardError("repository binding requires an explicit remote")
    identity = None
    if selected is not None:
        if not isinstance(selected, str) or selected not in names:
            raise BoardError("repository binding remote is unavailable or ambiguous")
        # Inspect both configured and rewritten transport URLs before the
        # existing identity helper has an opportunity to strip private data.
        for command in (("config", "--get-all", f"remote.{selected}.url"),
                        ("remote", "get-url", "--all", "--", selected),
                        ("remote", "get-url", "--push", "--all", "--", selected)):
            url = _optional_git_value(_git(repo, *command))
            if url is None or any(c.isspace() for c in url) or any(c in url for c in "?#"):
                raise BoardError("repository remote URL is unsafe")
            if SECRET_SHAPE_RE.search(url):
                raise BoardError("repository remote URL is unsafe")
            if "://" in url:
                from urllib.parse import unquote, urlsplit
                try:
                    parsed = urlsplit(url)
                    parsed.port  # Reject malformed ports rather than normalizing them away.
                except ValueError as exc:
                    raise BoardError("repository remote URL is malformed") from exc
                if (parsed.scheme not in {"https", "http", "ssh", "git"}
                    or parsed.password is not None
                    or (parsed.username is not None and parsed.scheme != "ssh")
                    or SECRET_SHAPE_RE.search(unquote(url))):
                    raise BoardError("repository remote URL is unsafe")
        try:
            endpoint = _remote_claim.remote_endpoint(repo, selected)
        except (ValueError, _remote_claim.RemoteClaimError) as exc:
            raise BoardError("repository remote identity is unavailable or ambiguous") from exc
        if endpoint is None:
            raise BoardError("repository remote identity is unavailable")
        identity = endpoint[1]
    binding = {"common_dir_sha256": hashlib.sha256(str(Path(common).resolve()).encode("utf-8")).hexdigest(),
               "remote_identity": identity}
    return _validate_repository_binding(binding)


def _scope_snapshot(repo: Path, values: list[str]) -> tuple[list[str], dict]:
    """Return lexical scope and transient identity witnesses for its parents."""
    if not isinstance(values, list) or len(values) > 256:
        raise BoardError("claim write scope must be a bounded list")
    for value in values:
        _validate_write_scope([value])
    normalized = sorted(set(values))
    witnesses: dict[str, tuple[int, int, int] | None] = {}
    if not normalized:
        return normalized, witnesses
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        root_fd = os.open(repo, flags)
    except OSError as exc:
        raise BoardError("scope worktree must be a real directory") from exc
    try:
        root_stat = os.fstat(root_fd)
        witnesses["."] = (root_stat.st_dev, root_stat.st_ino, root_stat.st_mode)
        for prefix in normalized:
            cursor = os.dup(root_fd)
            components = []
            try:
                for component in prefix.split("/")[:-1]:
                    components.append(component)
                    relative = "/".join(components)
                    try:
                        child = os.open(component, flags, dir_fd=cursor)
                    except FileNotFoundError:
                        if relative in witnesses and witnesses[relative] is not None:
                            raise BoardError("scope component disappeared during normalization")
                        witnesses[relative] = None
                        break  # A new lexical subtree has no existing links to follow.
                    except OSError as exc:
                        raise BoardError("scope parent is a symlink or not a directory") from exc
                    os.close(cursor)
                    cursor = child
                    info = os.fstat(cursor)
                    observed = (info.st_dev, info.st_ino, info.st_mode)
                    if relative in witnesses and witnesses[relative] != observed:
                        raise BoardError("scope component changed during normalization")
                    witnesses[relative] = observed
            finally:
                os.close(cursor)
    finally:
        os.close(root_fd)
    return normalized, witnesses


def normalize_write_scope(repo: Path, values: list[str]) -> list[str]:
    """Normalize lexical scopes and inspect parents through no-follow descriptors."""
    return _scope_snapshot(repo, values)[0]


_HUDDLE_REF_FIELDS = {"entity", "row", "claim_revision", "owner", "claimed_at"}
_HUDDLE_FIELDS = {"id", "state", "reason", "opened_revision", "generation", "opened_at",
                  "reply_by", "round", "claims", "edges", "holds", "bids", "resolution",
                  "compliance", "remote_transition", "resolved_at", "retain_until"}
_HUDDLE_REASONS = {"write_scope_overlap", "scope_request", "semantic_suspicion"}
_EDGE_KINDS = {"path_overlap", "scope_unknown", "semantic_suspicion"}
_HUDDLE_STATES = {"awaiting_scope", "open_round_1", "open_round_2", "remote_pending", "awaiting_compliance", "resolved"}
_BID_ROLES = {"own", "disjoint", "review", "prove", "yield", "stand_down", "unavailable"}
_BID_REASONS = {"existing_claim", "path_disjoint", "distinct_outcome", "duplicate_intent", "best_proof_access",
                "blocked", "preserve_existing_diff", "owner_authorized_handoff", "transport_unavailable"}
_BID_REQUEST_FIELDS = {"seat", "claim", "role", "scope", "reason", "target", "support_claim", "evidence",
                       "round", "expected_huddle_generation"}


def _claim_ref(claim: dict) -> dict:
    return {key: claim[key] for key in _HUDDLE_REF_FIELDS}


def _valid_claim_ref(ref: object) -> bool:
    return (isinstance(ref, dict) and set(ref) == _HUDDLE_REF_FIELDS
            and type(ref["claim_revision"]) is int
            and all(isinstance(ref[k], str) for k in _HUDDLE_REF_FIELDS - {"claim_revision"}))


def _claim_key(claim: dict) -> tuple:
    return (claim["entity"], claim["row"], claim["claim_revision"], claim["owner"])


def _claim_rank(claim: dict) -> tuple:
    if claim["claim_revision"] == 0:
        return (0, claim["claimed_at"], claim["entity"], claim["row"], claim["owner"])
    return (1, claim["claim_revision"], claim["entity"], claim["row"], claim["owner"])


def _path_overlap(left: str, right: str) -> bool:
    return left == "." or right == "." or left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _same_repository(a: dict, b: dict) -> bool:
    _validate_repository_binding(a)
    _validate_repository_binding(b)
    same_common = a["common_dir_sha256"] == b["common_dir_sha256"]
    same_remote = a["remote_identity"] is not None and a["remote_identity"] == b["remote_identity"]
    if same_common and a["remote_identity"] != b["remote_identity"]:
        raise BoardError("repository bindings contradict one another")
    return same_common or same_remote


def _scope_edge(left: dict, right: dict) -> list[str]:
    a, b = left["repository_binding"], right["repository_binding"]
    if left["access"] == "read_only" or right["access"] == "read_only" or a is None or b is None:
        return []
    if not _same_repository(a, b):
        return []
    if "unscoped" in {left["access"], right["access"]}:
        return ["scope_unknown"]
    return ["path_overlap"] if any(_path_overlap(a, b) for a in left["write_scope"] for b in right["write_scope"]) else []


def claim_holds(huddle: dict) -> list[dict]:
    """Greedy direct-edge selection; connectivity does not serialize writers."""
    conflicts = {frozenset((_claim_key(e["left"]), _claim_key(e["right"]))) for e in huddle["edges"]}
    selected, held = [], []
    for claim in sorted(huddle["claims"], key=_claim_rank):
        key = _claim_key(claim)
        if any(frozenset((key, prior)) in conflicts for prior in selected):
            held.append(claim)
        else:
            selected.append(key)
    return copy.deepcopy(held)


def _validate_huddle_reference(ref: object, revision: int) -> None:
    if (not _valid_claim_ref(ref) or ENTITY_ID.fullmatch(ref["entity"]) is None
        or ROW_ID.fullmatch(ref["row"]) is None or not 0 <= ref["claim_revision"] <= revision):
        raise BoardError("Huddle claim reference is malformed")
    validate_owner(ref["owner"])
    _timestamp(ref["claimed_at"], "Huddle claim time")


def _closed(value: object, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise BoardError(f"{label} has unknown or missing fields")


def _enum(value: object, allowed: set[str], label: str) -> None:
    if not isinstance(value, str) or value not in allowed:
        raise BoardError(f"{label} is unsupported")


def _digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _reference_list(value: object, revision: int, label: str, *, limit: int = 64) -> dict:
    if not isinstance(value, list) or len(value) > limit:
        raise BoardError(f"{label} exceeds its bound")
    for ref in value:
        _validate_huddle_reference(ref, revision)
    keys = {_claim_key(ref): ref for ref in value}
    if len(keys) != len(value) or value != sorted(value, key=_claim_rank):
        raise BoardError(f"{label} is duplicated or unordered")
    return keys


def _bid_digest(huddle_id: str, bid: dict) -> str:
    request = {"huddle_id": huddle_id, **{key: bid[key] for key in _BID_REQUEST_FIELDS}}
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _scope_subset(scope: list[str], authority: list[str]) -> bool:
    return all(any(old == "." or path == old or path.startswith(old + "/") for old in authority) for path in scope)


def _validate_bids(h: dict, payload: dict) -> None:
    bids = h["bids"]
    if not isinstance(bids, list) or len(bids) > 128:
        raise BoardError("Huddle bid cap exceeded")
    current = {_claim_key(c): c for c in payload["claims"]}
    keys = set()
    held = {_claim_key(c) for c in claim_holds(h)}
    for bid in bids:
        _closed(bid, _BID_REQUEST_FIELDS | {"bid_digest", "submitted_at"}, "Huddle bid")
        _validate_huddle_reference(bid["claim"], payload["revision"])
        if bid["claim"] not in h["claims"] or bid["seat"] != bid["claim"]["owner"]:
            raise BoardError("Huddle bid does not name its exact participant owner")
        _enum(bid["role"], _BID_ROLES, "Huddle bid role")
        _enum(bid["reason"], _BID_REASONS, "Huddle bid reason")
        if (type(bid["round"]) is not int or bid["round"] not in (1, 2) or bid["round"] > h["round"]
            or type(bid["expected_huddle_generation"]) is not int
            or not 1 <= bid["expected_huddle_generation"] <= h["generation"]):
            raise BoardError("Huddle bid round or generation is invalid")
        key = (_claim_key(bid["claim"]), bid["round"])
        if key in keys:
            raise BoardError("Huddle contains a duplicate bid key")
        keys.add(key)
        submitted = _timestamp(bid["submitted_at"], "Huddle bid time")
        if submitted < _timestamp(h["opened_at"], "Huddle opening time"):
            raise BoardError("Huddle bid predates opening")
        _validate_write_scope(bid["scope"])
        _closed(bid["evidence"], {"kind", "value"}, "Huddle evidence")
        _enum(bid["evidence"]["kind"], {"claim", "plan_row", "progress_receipt", "source_commit", "none"}, "Huddle evidence kind")
        evidence = bid["evidence"]["value"]
        if not isinstance(evidence, str) or not (evidence == "self" or _digest(evidence)
            or (bid["evidence"]["kind"] == "source_commit" and GIT_OBJECT_ID.fullmatch(evidence))
            or (bid["evidence"]["kind"] == "plan_row" and ROW_ID.fullmatch(evidence))):
            raise BoardError("Huddle evidence must be a path-free identifier")
        if bid["role"] == "yield":
            _validate_huddle_reference(bid["target"], payload["revision"])
            if (bid["target"] not in h["claims"] or bid["target"] == bid["claim"]
                or bid["target"]["owner"] == bid["seat"] or bid["reason"] != "owner_authorized_handoff"):
                raise BoardError("Huddle yield target is incompatible")
        elif bid["target"] is not None:
            raise BoardError("only yield may name a target")
        if bid["role"] in {"review", "prove"}:
            _validate_huddle_reference(bid["support_claim"], payload["revision"])
            if bid["support_claim"]["owner"] != bid["seat"] or bid["support_claim"] in h["claims"]:
                raise BoardError("Huddle support must be a distinct same-owner claim")
        elif bid["support_claim"] is not None:
            raise BoardError("only support roles may name a support claim")
        if bid["role"] in {"own", "disjoint"} and not bid["scope"]:
            raise BoardError("continuing bid requires nonempty write scope")
        active = h["state"] in {"open_round_1", "open_round_2"} and bid["expected_huddle_generation"] == h["generation"]
        if active:
            claim = current.get(key[0])
            if claim is None or _claim_ref(claim) != bid["claim"]:
                raise BoardError("active bid participant is not current")
            selected = key[0] not in held
            if (selected and bid["role"] not in {"own", "disjoint", "yield", "unavailable"}
                or not selected and bid["role"] == "yield"):
                raise BoardError("Huddle bid role disagrees with graph authority")
            if h["reply_by"] is not None and submitted >= _timestamp(h["reply_by"], "Huddle deadline"):
                raise BoardError("active bid is at or beyond its deadline")
            if bid["role"] in {"review", "prove"}:
                support = current.get(_claim_key(bid["support_claim"]))
                if (support is None or _claim_ref(support) != bid["support_claim"]
                    or bid["scope"] != support["write_scope"]
                    or bid["role"] == "review" and support["access"] != "read_only"):
                    raise BoardError("Huddle support access or scope is invalid")
            elif bid["role"] == "disjoint":
                if not _scope_subset(bid["scope"], claim["write_scope"]):
                    raise BoardError("Huddle disjoint bid expands scope")
            elif bid["scope"] != claim["write_scope"]:
                raise BoardError("Huddle bid must repeat current scope")
        if not _digest(bid["bid_digest"]) or bid["bid_digest"] != _bid_digest(h["id"], bid):
            raise BoardError("Huddle bid digest disagrees with its request")


def _validate_transfer(value: dict, h: dict, revision: int) -> None:
    for field in ("source_claim", "successor_claim", "target_prior_claim"):
        _validate_huddle_reference(value[field], revision)
    source, successor, target = (value[k] for k in ("source_claim", "successor_claim", "target_prior_claim"))
    if (source not in h["claims"] or target not in h["claims"] or source == target
        or source["owner"] == target["owner"] or successor != {**source, "owner": target["owner"]}
        or value["target_prior_action"] != "return_required"):
        raise BoardError("Huddle handoff identities or disposition are inconsistent")
    paired = any(a["claim"] == source and a["role"] == "yield" and a["target"] == target and a["round"] == h["round"]
        and a["reason"] == "owner_authorized_handoff" and any(b["claim"] == target and b["role"] == "own"
            and b["reason"] == "owner_authorized_handoff" and b["round"] == a["round"] for b in h["bids"])
        for a in h["bids"])
    if not paired or source in claim_holds(h) or target not in claim_holds(h):
        raise BoardError("Huddle handoff lacks a selected-owner and target bid pair")


def _validate_remote_transition(h: dict, revision: int) -> None:
    remote = h["remote_transition"]
    if remote is None:
        return
    _closed(remote, {"source_claim", "successor_claim", "target_prior_claim", "target_prior_action",
        "remote_ref", "expected_remote_version", "readback", "attempt_receipt"}, "Huddle remote transition")
    _validate_transfer(remote, h, revision)
    source = remote["source_claim"]
    if (remote["remote_ref"] != _remote_claim.claim_ref(source["entity"], source["row"])
        or not isinstance(remote["expected_remote_version"], str)
        or _remote_claim.HEX_OBJECT.fullmatch(remote["expected_remote_version"]) is None):
        raise BoardError("Huddle remote claim reference or version is invalid")
    _enum(remote["readback"], {"not_attempted", "ambiguous", "predecessor", "successor"}, "Huddle remote readback")
    if ((remote["readback"] == "not_attempted" and remote["attempt_receipt"] is not None)
        or remote["readback"] != "not_attempted" and not _digest(remote["attempt_receipt"])):
        raise BoardError("Huddle remote attempt receipt is inconsistent")


def _validate_resolution(h: dict, payload: dict) -> set:
    revision = payload["revision"]
    resolution = h["resolution"]
    fields = {"settled_revision", "settled_at", "rule", "handoff", "write_owners", "actions", "support_actions"}
    _closed(resolution, fields, "Huddle resolution")
    if (type(resolution["settled_revision"]) is not int
        or not h["opened_revision"] <= resolution["settled_revision"] <= revision):
        raise BoardError("Huddle settlement revision is inconsistent")
    _enum(resolution["rule"], {"exact_claim_owner", "path_disjoint", "earliest_valid_claim",
        "owner_authorized_handoff", "proof_first_stale_recovery"}, "Huddle resolution rule")
    settled = _timestamp(resolution["settled_at"], "Huddle settlement time")
    if settled < _timestamp(h["opened_at"], "Huddle opening time"):
        raise BoardError("Huddle settlement predates opening")
    if h["state"] == "resolved":
        resolved = _timestamp(h["resolved_at"], "Huddle resolution time")
        if resolved < settled or _timestamp(h["retain_until"], "Huddle retention") != resolved + timedelta(hours=24):
            raise BoardError("Huddle resolution or retention time is inconsistent")
    if not isinstance(resolution["actions"], list) or len(resolution["actions"]) != len(h["claims"]):
        raise BoardError("Huddle resolution must dispose every participant exactly once")
    actions = {}
    for action in resolution["actions"]:
        _closed(action, {"claim", "action"}, "Huddle participant action")
        _validate_huddle_reference(action["claim"], revision)
        _enum(action["action"], {"continue", "continue_disjoint", "handoff_complete", "return_required"}, "Huddle participant action")
        key = _claim_key(action["claim"])
        if action["claim"] not in h["claims"] or key in actions:
            raise BoardError("Huddle action names an absent or duplicated participant")
        actions[key] = action["action"]
    owners = _reference_list(resolution["write_owners"], revision, "Huddle write owners")
    handoff = resolution["handoff"]
    if resolution["rule"] == "owner_authorized_handoff":
        _closed(handoff, {"source_claim", "successor_claim", "target_prior_claim", "target_prior_action", "mode", "remote_readback"}, "Huddle handoff")
        _validate_transfer(handoff, h, revision)
        _enum(handoff["mode"], {"local", "remote"}, "Huddle handoff mode")
        if ((handoff["mode"] == "local" and (handoff["remote_readback"] is not None or h["remote_transition"] is not None))
            or handoff["mode"] == "remote" and (handoff["remote_readback"] != "successor"
                or h["remote_transition"] is None or h["remote_transition"]["readback"] != "successor"
                or any(handoff[k] != h["remote_transition"][k] for k in
                    ("source_claim", "successor_claim", "target_prior_claim", "target_prior_action")))):
            raise BoardError("Huddle handoff mode and remote readback disagree")
        if (actions[_claim_key(handoff["source_claim"])] != "handoff_complete"
            or actions[_claim_key(handoff["target_prior_claim"])] != "return_required"):
            raise BoardError("Huddle handoff dispositions disagree")
    elif handoff is not None or "handoff_complete" in actions.values():
        raise BoardError("non-handoff resolution cannot transfer authority")
    selected = {_claim_key(c) for c in h["claims"]} - {_claim_key(c) for c in claim_holds(h)}
    selected -= {_claim_key(b["claim"]) for b in h["bids"] if b["round"] == h["round"]
                 and b["role"] in {"stand_down", "review", "prove"}}
    continuing = {key for key, action in actions.items() if action != "return_required"}
    if continuing != selected:
        raise BoardError("Huddle dispositions disagree with graph selection")
    if resolution["rule"] == "path_disjoint" and (h["edges"] or set(actions.values()) != {"continue_disjoint"}):
        raise BoardError("path-disjoint resolution retains conflicts or wrong dispositions")
    if resolution["rule"] == "exact_claim_owner" and len(h["claims"]) != 1:
        raise BoardError("exact-owner resolution requires one surviving participant")
    allowed = {key: ref for ref in h["claims"] if (key := _claim_key(ref)) in continuing}
    if handoff:
        allowed.pop(_claim_key(handoff["source_claim"]))
        allowed[_claim_key(handoff["successor_claim"])] = handoff["successor_claim"]
    if any(allowed.get(key) != ref for key, ref in owners.items()):
        raise BoardError("Huddle writer lacks a continuing disposition")
    current = {_claim_key(c): c for c in payload["claims"]}
    for key, ref in allowed.items():
        if h["state"] != "resolved" and key in current and ((_claim_ref(current[key]) != ref) or (current[key]["access"] == "write") != (key in owners)):
            raise BoardError("Huddle write owners disagree with current access")
    support = resolution["support_actions"]
    if not isinstance(support, list) or len(support) > 64:
        raise BoardError("Huddle support action cap exceeded")
    support_keys = set()
    for action in support:
        _closed(action, {"participant_claim", "support_claim", "action"}, "Huddle support action")
        for field in ("participant_claim", "support_claim"):
            _validate_huddle_reference(action[field], revision)
        _enum(action["action"], {"review_claim", "prove_claim"}, "Huddle support action")
        key = _claim_key(action["participant_claim"])
        if (key in support_keys or action["participant_claim"] not in h["claims"]
            or action["support_claim"] in h["claims"]
            or action["participant_claim"]["owner"] != action["support_claim"]["owner"]
            or not any(b["claim"] == action["participant_claim"] and b["support_claim"] == action["support_claim"]
                and b["role"] + "_claim" == action["action"] and b["round"] == h["round"] for b in h["bids"])):
            raise BoardError("Huddle support action lacks its exact matching bid")
        support_keys.add(key)
    compliance = h["compliance"]
    if not isinstance(compliance, list) or len(compliance) > 64:
        raise BoardError("Huddle compliance cap exceeded")
    required = {key for key, action in actions.items() if action == "return_required"}
    entries, pending = set(), set()
    for entry in compliance:
        _closed(entry, {"claim", "required", "plan_root_at_settlement", "status", "completion"}, "Huddle compliance")
        _validate_huddle_reference(entry["claim"], revision)
        key = _claim_key(entry["claim"])
        if (entry["claim"] not in h["claims"] or key in entries or key not in required
            or entry["required"] != "canonical_disposition_then_return" or not _digest(entry["plan_root_at_settlement"])):
            raise BoardError("Huddle compliance identity or plan root is inconsistent")
        entries.add(key)
        _enum(entry["status"], {"pending", "satisfied"}, "Huddle compliance status")
        if entry["status"] == "pending":
            if entry["completion"] is not None or key not in current or _claim_ref(current[key]) != entry["claim"]:
                raise BoardError("pending compliance lacks its exact current claim")
            pending.add(key)
        else:
            completion = entry["completion"]
            _closed(completion, {"kind", "board_revision", "receipt"}, "Huddle compliance completion")
            _enum(completion["kind"], {"return", "proof_first_stale_recovery"}, "Huddle completion kind")
            if (key in current or type(completion["board_revision"]) is not int
                or not resolution["settled_revision"] < completion["board_revision"] <= revision
                or not (completion["receipt"] == "self" or _digest(completion["receipt"]))):
                raise BoardError("Huddle compliance completion is inconsistent")
    if entries != required:
        raise BoardError("every required return needs exactly one compliance entry")
    return pending


def _validate_huddles(payload: dict, *, pending_retention: bool = False) -> None:
    """Decode all lifecycle states without advancing deadlines or pruning history."""
    records = payload["huddles"]
    if not isinstance(records, list) or len(records) > 80:
        raise BoardError("Huddle record cap exceeded")
    current = {_claim_key(c): c for c in payload["claims"]}
    ids, members = set(), set()
    live_count = retained_count = 0
    for h in records:
        if not isinstance(h, dict) or set(h) != _HUDDLE_FIELDS:
            raise BoardError("Huddle has unknown or missing fields")
        if not isinstance(h["id"], str) or re.fullmatch(r"hdl_[0-9a-f]{8}", h["id"]) is None or h["id"] in ids:
            raise BoardError("Huddle id is invalid or duplicated")
        ids.add(h["id"])
        _enum(h["state"], _HUDDLE_STATES, "Huddle state")
        resolved = h["state"] == "resolved"
        settled = h["state"] in {"awaiting_compliance", "resolved"}
        open_state = h["state"] in {"awaiting_scope", "open_round_1", "open_round_2"}
        retained_count += int(resolved)
        live_count += int(not resolved)
        if live_count > 16 or retained_count > (65 if pending_retention else 64):
            raise BoardError("live or retained Huddle cap exceeded")
        if not isinstance(h["reason"], str) or h["reason"] not in _HUDDLE_REASONS:
            raise BoardError("Huddle reason is invalid")
        for field in ("opened_revision", "generation"):
            if type(h[field]) is not int or not 1 <= h[field] <= payload["revision"]:
                raise BoardError("Huddle revision or generation is invalid")
        opened = _timestamp(h["opened_at"], "Huddle open time")
        if open_state:
            if _timestamp(h["reply_by"], "Huddle deadline") <= opened:
                raise BoardError("Huddle deadline must follow opening")
        elif h["reply_by"] is not None:
            raise BoardError("Huddle terminal or pending state cannot have a deadline")
        if type(h["round"]) is not int or h["round"] not in (0, 1, 2):
            raise BoardError("Huddle round is invalid")
        if not isinstance(h["claims"], list) or not (1 if settled else 2) <= len(h["claims"]) <= 64:
            raise BoardError("Huddle participant cap or minimum violated")
        refs = {}
        for ref in h["claims"]:
            _validate_huddle_reference(ref, payload["revision"])
            key = _claim_key(ref)
            if key in refs or (not resolved and key in members):
                raise BoardError("claim belongs to more than one live Huddle")
            refs[key] = ref
        if not resolved:
            members.update(refs)
        if h["claims"] != sorted(h["claims"], key=_claim_rank):
            raise BoardError("Huddle claims are not canonically ordered")
        if not isinstance(h["edges"], list) or not (0 if settled else 1) <= len(h["edges"]) <= 2016:
            raise BoardError("Huddle edge cap or minimum violated")
        pairs = set()
        for edge in h["edges"]:
            if not isinstance(edge, dict) or set(edge) != {"left", "right", "kinds"}:
                raise BoardError("Huddle edge fields are invalid")
            if any(not _valid_claim_ref(edge[k]) or edge[k] not in h["claims"] for k in ("left", "right")):
                raise BoardError("Huddle edge points outside its claims")
            if _claim_rank(edge["left"]) >= _claim_rank(edge["right"]):
                raise BoardError("Huddle edge endpoints are not ordered")
            pair = (_claim_key(edge["left"]), _claim_key(edge["right"]))
            kinds = edge["kinds"]
            if (not isinstance(kinds, list) or not kinds or any(not isinstance(k, str) or k not in _EDGE_KINDS for k in kinds)
                or kinds != sorted(set(kinds)) or pair in pairs):
                raise BoardError("Huddle edge kinds or uniqueness are invalid")
            pairs.add(pair)
            if not resolved and all(key in current for key in pair):
                actual = _scope_edge(current[pair[0]], current[pair[1]])
                if sorted(k for k in kinds if k != "semantic_suspicion") != actual:
                    raise BoardError("Huddle path edges disagree with current declarations")
        ordered_refs = h["claims"]
        for index, left in enumerate(ordered_refs):
            for right in ordered_refs[index + 1:]:
                pair = (_claim_key(left), _claim_key(right))
                if (not resolved and all(key in current for key in pair)
                    and _scope_edge(current[pair[0]], current[pair[1]]) and pair not in pairs):
                    raise BoardError("Huddle is missing a current scope edge")
        ordered = sorted(h["edges"], key=lambda e: (_claim_rank(e["left"]), _claim_rank(e["right"])))
        if h["edges"] != ordered:
            raise BoardError("Huddle edges are not canonically ordered")
        _reference_list(h["holds"], payload["revision"], "Huddle holds", limit=65 if h["state"] == "remote_pending" else 64)
        unknown = any("scope_unknown" in e["kinds"] for e in h["edges"])
        if (h["state"] == "awaiting_scope" and (not unknown or h["round"] != 0 or h["bids"] != [])
            or h["state"] in {"open_round_1", "open_round_2"} and (unknown or h["round"] != int(h["state"][-1]))
            or h["state"] == "remote_pending" and h["round"] not in (1, 2)):
            raise BoardError("Huddle state disagrees with round or scope edges")
        _validate_bids(h, payload)
        _validate_remote_transition(h, payload["revision"])
        if not resolved and (h["resolved_at"] is not None or h["retain_until"] is not None):
            raise BoardError("live Huddle cannot have resolution timestamps")
        if not settled:
            if h["resolution"] is not None or h["compliance"] != []:
                raise BoardError("unsettled Huddle has resolution or compliance")
            expected_holds = claim_holds(h)
            if h["state"] == "remote_pending":
                remote = h["remote_transition"]
                if remote is None or remote["readback"] not in {"not_attempted", "ambiguous"}:
                    raise BoardError("pending remote Huddle needs unresolved readback")
                # The successor is not installed locally yet. Its exact transfer
                # reference is nevertheless held alongside the predecessor.
                held = {_claim_key(c): c for c in expected_holds}
                for field in ("source_claim", "successor_claim"):
                    held[_claim_key(remote[field])] = remote[field]
                expected_holds = sorted(held.values(), key=_claim_rank)
            elif h["remote_transition"] is not None:
                raise BoardError("open Huddle cannot have a remote transition")
        else:
            if h["remote_transition"] is not None and h["remote_transition"]["readback"] not in {"successor", "predecessor"}:
                raise BoardError("settled Huddle cannot have unresolved remote ownership")
            pending = _validate_resolution(h, payload)
            if bool(pending) != (h["state"] == "awaiting_compliance"):
                raise BoardError("Huddle state disagrees with pending compliance")
            expected_holds = sorted((refs[key] for key in pending), key=_claim_rank)
        if h["holds"] != expected_holds:
            raise BoardError("Huddle holds disagree with state authority")
        if not resolved:
            historical = set()
            if settled:
                historical.update(_claim_key(e["claim"]) for e in h["compliance"] if e["status"] == "satisfied")
                resolution = h["resolution"]
                actions = {_claim_key(action["claim"]): action["action"]
                           for action in resolution["actions"]}
                writer_keys = {_claim_key(ref) for ref in resolution["write_owners"]}
                # A proof-first stale close can remove only a continuing writer
                # while a different participant remains pending compliance.
                historical.update(
                    key for key in writer_keys
                    if key not in current and actions.get(key) in {
                        "continue", "continue_disjoint", "handoff_complete",
                    }
                )
                handoff = resolution["handoff"]
                if handoff:
                    historical.add(_claim_key(handoff["source_claim"]))
                    successor = handoff["successor_claim"]
                    key = _claim_key(successor)
                    if key in current and (_claim_ref(current[key]) != successor or key in members):
                        raise BoardError("Huddle successor is not its unique current source claim")
                    if key in current:
                        members.add(key)
                    elif key not in writer_keys:
                        raise BoardError("Huddle successor is not an authorized continuing writer")
            for key, ref in refs.items():
                if key not in historical and (key not in current or _claim_ref(current[key]) != ref or current[key]["access"] == "read_only"):
                    raise BoardError("Huddle reference is not a current source claim")
        if len(json.dumps(h, sort_keys=True, separators=(",", ":")).encode("utf-8")) > 4 * 1024 * 1024:
            raise BoardError("Huddle encoded size cap exceeded")
    for h in records:
        if h["state"] == "resolved":
            continue
        for bid in h["bids"]:
            support = bid["support_claim"]
            if support is not None and bid["round"] == h["round"]:
                key = _claim_key(support)
                if key in members or key not in current or _claim_ref(current[key]) != support:
                    raise BoardError("Huddle support must remain current outside every live Huddle")


def _validate_v2(payload: object, *, pending_retention: bool = False) -> dict:
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "revision", "projects", "entities", "claims", "huddles"
    }:
        raise BoardError("board has unknown or missing top-level fields")
    if payload["schema"] != V2_SCHEMA:
        raise BoardError("board schema is not supported")
    if not isinstance(payload["claims"], list):
        raise BoardError("board projects, entities, and claims must be lists")
    claim_fields = {
        "entity", "row", "owner", "claimed_at", "return_by", "recovery",
        "claim_revision", "access", "repository_binding", "write_scope",
    }
    old_claim_fields = {
        "entity", "row", "owner", "claimed_at", "return_by", "recovery",
    }
    for claim in payload["claims"]:
        if not isinstance(claim, dict) or set(claim) != claim_fields:
            raise BoardError("claims have unknown or missing fields")

    v1_projection = {
        "schema": V1_SCHEMA,
        "revision": payload["revision"],
        "projects": payload["projects"],
        "entities": payload["entities"],
        "claims": [
            {key: claim[key] for key in old_claim_fields}
            for claim in payload["claims"]
        ],
    }
    _validate_v1(v1_projection)

    for claim in payload["claims"]:
        claim_revision = claim["claim_revision"]
        if (
            isinstance(claim_revision, bool)
            or not isinstance(claim_revision, int)
            or claim_revision < 0
            or claim_revision > payload["revision"]
        ):
            raise BoardError("claim revision must be a current nonnegative integer")
        access = claim["access"]
        if not isinstance(access, str) or access not in {"unscoped", "read_only", "write"}:
            raise BoardError("claim access is not supported")
        scope = _validate_write_scope(claim["write_scope"])
        binding = claim["repository_binding"]

        if access == "read_only":
            if binding is not None or scope:
                raise BoardError("read-only claims must be unbound with empty scope")
        elif access == "unscoped":
            if binding is not None or claim_revision != 0:
                _validate_repository_binding(binding)
            if scope:
                raise BoardError("unscoped claims must have empty scope")
        else:
            _validate_repository_binding(binding)
            if not scope:
                raise BoardError("write claims must have nonempty scope")

    _validate_huddles(payload, pending_retention=pending_retention)
    return payload


def _validate(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise BoardError("board has unknown or missing top-level fields")
    schema = payload.get("schema")
    if schema == V1_SCHEMA:
        return _validate_v1(payload)
    if schema == V2_SCHEMA:
        return _validate_v2(payload)
    raise BoardError("board schema is not supported")


def migrate_v1_to_v2(payload: dict) -> dict:
    """Return a strict, lossless v2 projection without changing its source."""
    _validate_v1(payload)
    migrated = copy.deepcopy(payload)
    migrated["schema"] = V2_SCHEMA
    for claim in migrated["claims"]:
        claim.update({
            "claim_revision": 0,
            "access": "unscoped",
            "repository_binding": None,
            "write_scope": [],
        })
    migrated["huddles"] = []
    return _validate_v2(migrated)


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict:
    value: dict = {}
    for key, item in pairs:
        if key in value:
            raise BoardError("board JSON contains duplicate object keys")
        value[key] = item
    return value


def _decode(path: Path) -> dict:
    if path.is_symlink():
        raise BoardError("board file must not be a symlink")
    try:
        return _validate(json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_json_object,
        ))
    except (OSError, UnicodeError, ValueError) as exc:
        raise BoardError("board file is unreadable or malformed") from exc


def _read(path: Path) -> dict:
    return _decode(path)


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise BoardError(f"{label} must be an ISO8601 Z timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise BoardError(f"{label} must be an ISO8601 Z timestamp") from exc
    return parsed.replace(tzinfo=timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def claim_is_stale(claim: dict, *, now: datetime | None = None) -> bool:
    """Derive expiry at read time; no heartbeat or background process."""
    current = now or datetime.now(timezone.utc)
    return _timestamp(claim.get("return_by"), "claim return-by") <= current


def _replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
    os.replace(source, destination)


def _encoded_board(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_bytes(path: Path, encoded: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".board.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        _replace(temporary, path)
        os.chmod(path, 0o600)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _write(path: Path, payload: dict) -> None:
    _write_bytes(path, _encoded_board(payload))


def _journal_head(root: Path) -> str:
    result = _git(root, "rev-parse", "--verify", "HEAD")
    if result.returncode or not result.stdout.strip():
        raise BoardError("root board journal head could not be read")
    return result.stdout.strip()


def _commit_parent(root: Path, revision: str) -> str | None:
    result = _git(root, "rev-list", "--parents", "-n", "1", revision)
    if result.returncode:
        raise BoardError("root board journal ancestry could not be read")
    parts = result.stdout.split()
    if len(parts) == 1:
        return None
    if len(parts) != 2:
        raise BoardError("root board journal ancestry is not linear")
    return parts[1]


def _journal_parent(root: Path) -> str | None:
    return _commit_parent(root, "HEAD")


def _is_expected_board_commit(
    root: Path,
    revision: str,
    *,
    parent: str,
    encoded: bytes,
    message: str,
) -> bool:
    try:
        if _commit_parent(root, revision) != parent:
            return False
    except BoardError:
        return False
    changed = _git(
        root,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        revision,
    )
    published = _git(root, "show", f"{revision}:{BOARD_NAME}")
    subject = _git(root, "show", "-s", "--format=%s", revision)
    return (
        not changed.returncode
        and changed.stdout.splitlines() == [BOARD_NAME]
        and not published.returncode
        and published.stdout.encode("utf-8") == encoded
        and not subject.returncode
        and subject.stdout.strip() == message
    )


def _journal_update_reference(root: Path) -> str:
    symbolic = _git(root, "symbolic-ref", "--quiet", "HEAD")
    if symbolic.returncode == 0:
        reference = symbolic.stdout.strip()
        checked = _git(root, "check-ref-format", reference)
        if checked.returncode:
            raise BoardError("root board journal HEAD ref is malformed")
        return reference
    if symbolic.returncode == 1:
        return "HEAD"
    raise BoardError("root board journal HEAD ref could not be inspected")


def _git_ref_transaction(
    root: Path,
    commands: list[str],
) -> subprocess.CompletedProcess[bytes]:
    content = (
        "start\n"
        "option no-deref\n"
        + "\n".join(commands)
        + "\nprepare\ncommit\n"
    ).encode("ascii")
    return _git_bytes(root, "update-ref", "--stdin", content=content)


def _commit_consuming_ref(
    root: Path,
    message: str,
    *,
    before_head: str,
    reference: str,
    receipt_oid: str,
) -> tuple[str, str]:
    added = _git(root, "add", "--", BOARD_NAME)
    if added.returncode:
        raise BoardError("root board could not record its local receipt")
    tree = _git(root, "write-tree")
    if tree.returncode or GIT_OBJECT_ID.fullmatch(tree.stdout.strip()) is None:
        raise BoardError("root board journal tree could not be written")
    committed = _git(
        root,
        "-c",
        "commit.gpgSign=false",
        "commit-tree",
        tree.stdout.strip(),
        "-p",
        before_head,
        "-m",
        message,
    )
    revision = committed.stdout.strip()
    if (
        committed.returncode
        or GIT_OBJECT_ID.fullmatch(revision) is None
        or not _is_expected_board_commit(
            root,
            revision,
            parent=before_head,
            encoded=(root / BOARD_NAME).read_bytes(),
            message=message,
        )
    ):
        raise BoardError("root board journal commit could not be prepared")
    head_reference = _journal_update_reference(root)
    updated = _git_ref_transaction(
        root,
        [
            f"update {head_reference} {revision} {before_head}",
            f"delete {reference} {receipt_oid}",
        ],
    )
    if updated.returncode:
        raise BoardError(
            "init registration receipt changed before board registration"
        )
    _git(
        root,
        "-c", "maintenance.autoDetach=false",
        "-c", "gc.autoDetach=false",
        "maintenance", "run", "--auto", "--quiet", "--no-detach",
    )
    return revision, head_reference


def _write_and_commit(
    root: Path,
    path: Path,
    payload: dict,
    message: str,
    *,
    consume_ref: tuple[str, str] | None = None,
    guard: Callable[[], None] | None = None,
    now: datetime | None = None,
) -> None:
    """Publish one board value and its journal commit or restore both exactly."""
    if payload.get("schema") == V2_SCHEMA:
        # Validate even records about to expire: retention must never hide a
        # malformed transition. Only the transient 65th resolution is allowed.
        _validate_v2(payload, pending_retention=True)
        instant = now if now is not None else datetime.now(timezone.utc)
        retained = sorted(
            (h for h in payload["huddles"] if h["state"] == "resolved"
             and _timestamp(h["retain_until"], "Huddle retention") > instant),
            key=lambda h: (h["resolution"]["settled_revision"], h["id"]),
        )[-64:]
        keep = {h["id"] for h in retained}
        payload["huddles"] = [h for h in payload["huddles"]
                              if h["state"] != "resolved" or h["id"] in keep]
    _validate(payload)
    try:
        previous = path.read_bytes()
    except OSError as exc:
        raise BoardError("root board could not freeze its previous value") from exc
    before_head = _journal_head(root)
    encoded = _encoded_board(payload)
    published_head_reference: str | None = None
    try:
        _write_bytes(path, encoded)
        if guard is not None:
            guard()
        if consume_ref is None:
            _commit(root, message)
        else:
            reference, receipt_oid = consume_ref
            _, published_head_reference = _commit_consuming_ref(
                root,
                message,
                before_head=before_head,
                reference=reference,
                receipt_oid=receipt_oid,
            )
        if guard is not None:
            guard()
        if (
            path.read_bytes() != encoded
            or _git(root, "diff", "--quiet", "HEAD", "--", BOARD_NAME).returncode
            or (
                consume_ref is not None
                and _init_registration_oid(root, consume_ref[0]) is not None
            )
        ):
            raise BoardError("root board journal did not preserve the published value")
    except BaseException:
        try:
            if path.read_bytes() != previous:
                _write_bytes(path, previous)
            current_head = _journal_head(root)
            if current_head != before_head:
                if not _is_expected_board_commit(
                    root,
                    current_head,
                    parent=before_head,
                    encoded=encoded,
                    message=message,
                ):
                    raise BoardError(
                        "root board journal changed outside this transaction"
                    )
                if consume_ref is None:
                    restored_head = _git(
                        root,
                        "update-ref",
                        "-m",
                        "shadow board: roll back failed transaction",
                        "HEAD",
                        before_head,
                        current_head,
                    )
                else:
                    if published_head_reference is None:
                        published_head_reference = _journal_update_reference(root)
                    reference, receipt_oid = consume_ref
                    restored_head = _git_ref_transaction(
                        root,
                        [
                            f"update {published_head_reference} {before_head} {current_head}",
                            f"create {reference} {receipt_oid}",
                        ],
                    )
                if restored_head.returncode:
                    raise BoardError("root board journal ref could not be restored")
            staged = _git(
                root,
                "diff",
                "--cached",
                "--quiet",
                before_head,
                "--",
                BOARD_NAME,
            )
            if staged.returncode == 1:
                restored_index = _git(
                    root,
                    "reset",
                    "--quiet",
                    before_head,
                    "--",
                    BOARD_NAME,
                )
                if restored_index.returncode:
                    raise BoardError("root board journal index could not be restored")
            elif staged.returncode:
                raise BoardError("root board journal index could not be inspected")
            status = _git(root, "status", "--porcelain=v1", "--", BOARD_NAME)
            if (
                _journal_head(root) != before_head
                or path.read_bytes() != previous
                or status.returncode
                or status.stdout.strip()
                or (
                    consume_ref is not None
                    and _init_registration_oid(root, consume_ref[0]) != consume_ref[1]
                )
            ):
                raise BoardError(
                    "root board journal recovery did not restore exact state"
                )
        except BaseException as recovery_exc:
            raise BoardError(
                "root board journal failed and exact recovery also failed"
            ) from recovery_exc
        raise


def _initialize_git(root: Path) -> None:
    """Maintain a private crash-recovery journal for board pointers only."""
    git_dir = root / ".git"
    if git_dir.is_symlink() or (git_dir.exists() and not git_dir.is_dir()):
        raise BoardError("root board Git directory must not be a symlink or file")
    result = _git(root, "init", "--quiet")
    if result.returncode:
        raise BoardError("root board Git repository could not be initialized")
    index_lock = git_dir / "index.lock"
    if index_lock.exists() or index_lock.is_symlink():
        if index_lock.is_symlink() or not index_lock.is_file():
            raise BoardError("root board Git receipt lock is unsafe")
        raise BoardError(
            "root board Git receipt lock exists; verify no Git process owns it, "
            "remove it, and retry"
        )
    _git(root, "config", "user.name", "Shadow")
    _git(root, "config", "user.email", "shadow@localhost")
    exclude = root / ".git" / "info" / "exclude"
    ignored = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    protected = {LOCK_NAME, "plans/", "archives/"}
    missing = [entry for entry in protected if entry not in ignored.splitlines()]
    if missing:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(ignored.rstrip("\n") + "\n" + "\n".join(missing) + "\n", encoding="utf-8")


def _commit(root: Path, message: str) -> None:
    """Journal board metadata only; plan files live outside this repository."""
    added = _git(root, "add", "--", BOARD_NAME)
    if added.returncode:
        raise BoardError("root board could not record its local receipt")
    if not _git(root, "diff", "--cached", "--quiet", "--", BOARD_NAME).returncode:
        return
    committed = _git(
        root,
        "-c", "core.hooksPath=/dev/null",
        "-c", "commit.gpgSign=false",
        "-c", "maintenance.autoDetach=false",
        "-c", "gc.autoDetach=false",
        "commit", "--quiet", "--only", "-m", message, "--", BOARD_NAME,
    )
    if committed.returncode:
        raise BoardError("root board could not journal its local receipt")


@contextmanager
def _transaction(home: Path | None = None) -> Iterator[tuple[Path, Path, dict]]:
    root = _safe_root(home)
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
    except OSError as exc:
        raise BoardError("root board directory could not be created or protected") from exc
    lock = root / LOCK_NAME
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock, flags, 0o600)
    except OSError as exc:
        raise BoardError("root board lock is unsafe or unavailable") from exc
    with os.fdopen(descriptor, "a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        _initialize_git(root)
        path = root / BOARD_NAME
        if path.exists() or path.is_symlink():
            payload = _decode(path)
            try:
                os.chmod(path, 0o600)
            except OSError as exc:
                raise BoardError("root board file could not be protected") from exc
            _commit(root, "shadow board: recover local authority")
        else:
            head = _git(root, "rev-parse", "--verify", "HEAD")
            if head.returncode == 0:
                historical = _git(root, "show", f"HEAD:{BOARD_NAME}")
                if historical.returncode:
                    raise BoardError("root board history exists but board.json is missing")
                try:
                    payload = _validate(json.loads(
                        historical.stdout, object_pairs_hook=_strict_json_object
                    ))
                except ValueError as exc:
                    raise BoardError("root board history contains malformed board.json") from exc
                _write(path, payload)
                _commit(root, "shadow board: restore missing local authority")
            else:
                payload = _empty()
                _write(path, payload)
                _commit(root, "shadow board: initialize this computer")
        try:
            yield root, path, payload
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def ensure(*, home: Path | None = None) -> dict:
    with _transaction(home) as (_, _, payload):
        return json.loads(json.dumps(payload))


def _huddle_id(opened_revision: int, claim_keys: list[tuple], edges: list[dict],
               reason: str, collision_counter: int) -> str:
    encoded = json.dumps([opened_revision, sorted(claim_keys), edges, reason, str(collision_counter)],
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "hdl_" + hashlib.sha256(encoded).hexdigest()[:8]


def _open_huddle(payload: dict, claim: dict, overlap: list[dict], reason: str, now: datetime,
                 *, scope_changed: bool = False) -> dict | None:
    if payload["schema"] != V2_SCHEMA:
        raise BoardError("Huddle graph requires v2; automatic activation is not available yet")
    if (not isinstance(reason, str) or reason not in _HUDDLE_REASONS or not isinstance(overlap, list)
        or (not overlap and not scope_changed)):
        raise BoardError("Huddle requires one supported reason and current peer claims")
    if len(overlap) > 63:
        raise BoardError("Huddle participant cap exceeded")
    current = {_claim_key(c): c for c in payload["claims"]}
    supplied = [claim, *overlap]
    for candidate in supplied:
        if (not isinstance(candidate, dict) or type(candidate.get("claim_revision")) is not int
            or candidate not in payload["claims"] or (candidate["access"] == "read_only" and not scope_changed)):
            raise BoardError("Huddle requires exact current source claims")
    keys = {_claim_key(c) for c in supplied}
    if len(keys) != len(supplied):
        raise BoardError("Huddle requires distinct current claims")
    primary = _claim_key(claim)
    # Discover omitted direct neighbors too: a caller cannot hide an overlap
    # or bypass the one-live-component rule by submitting a partial peer list.
    for candidate in payload["claims"]:
        if candidate is not claim and _scope_edge(claim, candidate):
            keys.add(_claim_key(candidate))
    existing = [h for h in payload["huddles"] if h["state"] != "resolved" and any(_claim_key(c) in keys for c in h["claims"])]
    if len(existing) > 1:
        raise BoardError("huddle_bridge: settle the earlier live Huddle before retrying")
    old = existing[0] if existing else None
    if old is not None:
        if old["state"] not in ("awaiting_scope", "open_round_1", "open_round_2"):
            raise BoardError("Huddle requires lifecycle recovery before changing membership")
        if now >= _timestamp(old["reply_by"], "Huddle deadline"):
            raise BoardError("Huddle deadline reached; settle before changing membership")
        keys.update(_claim_key(c) for c in old["claims"])
    elif sum(h["state"] != "resolved" for h in payload["huddles"]) >= 16:
        raise BoardError("live Huddle cap exceeded")
    if len(keys) > 64:
        raise BoardError("Huddle participant cap exceeded")
    claims = sorted((current[k] for k in keys if current[k]["access"] != "read_only"), key=_claim_rank)
    keys = {_claim_key(c) for c in claims}
    semantic = set()
    if old is not None:
        semantic.update(frozenset((_claim_key(e["left"]), _claim_key(e["right"])))
                        for e in old["edges"] if "semantic_suspicion" in e["kinds"])
    if reason == "semantic_suspicion" and not scope_changed:
        semantic.update(frozenset((primary, _claim_key(peer))) for peer in overlap)
    edges = []
    for index, left in enumerate(claims):
        for right in claims[index + 1:]:
            kinds = _scope_edge(left, right)
            if frozenset((_claim_key(left), _claim_key(right))) in semantic:
                kinds.append("semantic_suspicion")
            if kinds:
                edges.append({"left": _claim_ref(left), "right": _claim_ref(right), "kinds": sorted(kinds)})
    incident = {_claim_key(e[end]) for e in edges for end in ("left", "right")}
    prior_keys = {_claim_key(c) for c in old["claims"]} if old else set()
    if not (keys - prior_keys) <= incident:
        raise BoardError("Huddle participants must have a direct conflict edge")
    reachable = set(prior_keys) if old else {primary}
    pending = list(reachable)
    neighbors = {key: set() for key in keys}
    for edge in edges:
        left, right = _claim_key(edge["left"]), _claim_key(edge["right"])
        neighbors[left].add(right)
        neighbors[right].add(left)
    while pending:
        for neighbor in neighbors.get(pending.pop(), ()):
            if neighbor not in reachable:
                reachable.add(neighbor)
                pending.append(neighbor)
    if not keys <= reachable:
        raise BoardError("new Huddle participants must connect to the initiating claim or existing Huddle")
    refs = [_claim_ref(c) for c in claims]
    if old is not None and not scope_changed and old["claims"] == refs and old["edges"] == edges:
        return None
    opened_revision = payload["revision"] + 1
    if old is None:
        used = {h["id"] for h in payload["huddles"]}
        for counter in range(len(used) + 1):
            identifier = _huddle_id(opened_revision, list(keys), edges, reason, counter)
            if identifier not in used:
                break
        else:
            raise BoardError("Huddle identifier collision budget exhausted")
        huddle = {"id": identifier, "reason": reason, "opened_revision": opened_revision,
                  "generation": 1, "opened_at": _stamp(now)}
    else:
        huddle = copy.deepcopy(old)
        huddle["generation"] += 1
    unknown = any("scope_unknown" in edge["kinds"] for edge in edges)
    huddle.update(state="awaiting_scope" if unknown else "open_round_1", round=0 if unknown else 1,
                  reply_by=_stamp(now + timedelta(minutes=2)), claims=refs, edges=edges,
                  bids=[], resolution=None, compliance=[], remote_transition=None,
                  resolved_at=None, retain_until=None)
    huddle["holds"] = claim_holds(huddle)
    if not edges:
        huddle.update(state="resolved", round=old["round"] if old else 0, reply_by=None,
            resolved_at=_stamp(now), retain_until=_stamp(now + timedelta(hours=24)),
            resolution={"settled_revision": opened_revision, "settled_at": _stamp(now),
                "rule": "path_disjoint", "handoff": None,
                "write_owners": [_claim_ref(c) for c in claims if c["access"] == "write"],
                "actions": [{"claim": ref, "action": "continue_disjoint"} for ref in refs],
                "support_actions": []})
    if old is not None:
        payload["huddles"].remove(old)
    payload["huddles"].append(huddle)
    payload["huddles"].sort(key=lambda h: (h["opened_revision"], h["id"]))
    return huddle


def open_or_join_huddle(*, claim: dict, overlap: list[dict], reason: str,
                       now: datetime, home: Path | None = None) -> BoardMutation:
    with _transaction(home) as (root, path, payload):
        huddle = _open_huddle(payload, claim, overlap, reason, now)
        if huddle is None:
            return BoardMutation(copy.deepcopy(payload), False, None)
        payload["revision"] += 1
        _write_and_commit(root, path, payload, "shadow board: update Huddle graph", now=now)
        event = {"schema": "shadow.huddle-delivery-event.v1", "event": "huddle_changed",
                 "huddle_id": huddle["id"], "generation": huddle["generation"]}
        return BoardMutation(copy.deepcopy(payload), True, event)


def huddle_show(huddle_id: str, *, home: Path | None = None) -> dict:
    if not isinstance(huddle_id, str) or re.fullmatch(r"hdl_[0-9a-f]{8}", huddle_id) is None:
        raise BoardError("Huddle id is invalid")
    payload = snapshot(home=home)
    if payload is not None:
        for huddle in payload.get("huddles", []):
            if huddle["id"] == huddle_id:
                return copy.deepcopy(huddle)
    raise BoardError("Huddle was not found")


def _huddle_checkpoint(text: str, row: str) -> None:
    rows = [match for line in section_lines(text, "Tasks")
            if (match := _grammar.ROW_RE.fullmatch(line)) is not None and match.group("id") == row]
    if (len(rows) != 1 or row not in _grammar.candidate_row_ids(text)
        or not any(field.group("key") == "proof" and field.group("value").strip()
                   for field in _grammar.FIELD_RE.finditer(rows[0].group("tail")))):
        raise BoardError("Huddle checkpoint is not reachable in its canonical plan")


def submit_huddle_bid(*, huddle_id: str, seat: str, claim: dict, role: str,
                      scope: list[str], reason: str, target: dict | None,
                      support_claim: dict | None, evidence: dict, round: int,
                      expected_huddle_generation: int, now: datetime,
                      home: Path | None = None) -> BoardMutation:
    """Record structured intent without granting, shrinking or returning scope."""
    if not isinstance(huddle_id, str) or re.fullmatch(r"hdl_[0-9a-f]{8}", huddle_id) is None:
        raise BoardError("Huddle id is invalid")
    request = dict(seat=seat, claim=claim, role=role, scope=scope, reason=reason,
                   target=target, support_claim=support_claim, evidence=evidence,
                   round=round, expected_huddle_generation=expected_huddle_generation)
    with _transaction(home) as (root, path, payload):
        h = next((item for item in payload.get("huddles", []) if item["id"] == huddle_id), None)
        if h is None:
            raise BoardError("Huddle was not found")
        _validate_huddle_reference(claim, payload["revision"])
        if type(round) is not int or round not in (1, 2):
            raise BoardError("Huddle bid round is invalid")
        try:
            digest = _bid_digest(huddle_id, request)
        except (TypeError, ValueError, UnicodeError):
            raise BoardError("Huddle bid request is malformed") from None
        prior = next((bid for bid in h["bids"] if _claim_key(bid["claim"]) == _claim_key(claim)
                      and bid["round"] == round), None)
        if prior is not None:
            if digest != prior["bid_digest"]:
                raise BoardError("Huddle bid key replay has changed content")
            return BoardMutation(copy.deepcopy(payload), False, None)
        if (type(expected_huddle_generation) is not int
            or expected_huddle_generation != h["generation"]):
            raise BoardError("Huddle bid generation changed")
        if h["state"] not in {"open_round_1", "open_round_2"} or round != h["round"]:
            raise BoardError("Huddle is not accepting bids for this round")
        if now >= _timestamp(h["reply_by"], "Huddle deadline"):
            raise BoardError("Huddle bid deadline reached")
        bid = copy.deepcopy(request)
        bid.update(bid_digest=digest, submitted_at=_stamp(now))
        h["bids"].append(bid)
        _validate_bids(h, payload)
        support_plan = None
        support_bytes = None
        if support_claim is not None:
            support = next(c for c in payload["claims"] if _claim_ref(c) == support_claim)
            held = claim_holds(h)
            if any(_claim_ref(c) in h["claims"] and _claim_ref(c) not in held
                   and _scope_edge(support, c) for c in payload["claims"]):
                raise BoardError("Huddle support scope conflicts with a selected writer")
            entity = next(e for e in payload["entities"] if e["id"] == support_claim["entity"])
            support_plan = Path(entity["plan"])
            support_bytes = read_plan_bytes(support_plan)
            try:
                text = support_bytes.decode("utf-8")
            except UnicodeError:
                raise BoardError("Huddle support plan is not UTF-8") from None
            _huddle_checkpoint(text, support_claim["row"])
        payload["revision"] += 1
        def guard():
            if support_plan is not None and read_plan_bytes(support_plan) != support_bytes:
                raise BoardError("Huddle support plan changed during bid publication")
        _write_and_commit(root, path, payload, "shadow board: record Huddle bid", guard=guard, now=now)
        return BoardMutation(copy.deepcopy(payload), True, {
            "schema": "shadow.huddle-delivery-event.v1", "event": "huddle_changed",
            "huddle_id": h["id"], "generation": h["generation"]})


def bid_receipt(huddle_id: str, claim: dict, round: int, *, home: Path | None = None) -> dict:
    """Read the original immutable bid, even after its generation advanced."""
    h = huddle_show(huddle_id, home=home)
    if not _valid_claim_ref(claim) or type(round) is not int or round not in (1, 2):
        raise BoardError("Huddle bid key is invalid")
    for bid in h["bids"]:
        if bid["claim"] == claim and bid["round"] == round:
            return copy.deepcopy(bid)
    raise BoardError("Huddle bid was not found")


def settle_huddle(*, huddle_id: str, actor_claim: dict, expected_generation: int,
                  expected_board_revision: int, now: datetime,
                  home: Path | None = None) -> BoardMutation:
    """Commit a round decision without treating silence as a transfer."""
    with _transaction(home) as (root, path, payload):
        if (payload["schema"] != V2_SCHEMA or type(expected_board_revision) is not int
            or payload["revision"] != expected_board_revision):
            raise BoardError("Huddle settlement board revision changed")
        h = next((item for item in payload["huddles"] if item["id"] == huddle_id), None)
        if h is None or type(expected_generation) is not int or h["generation"] != expected_generation:
            raise BoardError("Huddle settlement generation changed")
        _validate_huddle_reference(actor_claim, payload["revision"])
        current = {_claim_key(c): c for c in payload["claims"]}
        if (actor_claim not in h["claims"] or _claim_key(actor_claim) not in current
            or _claim_ref(current[_claim_key(actor_claim)]) != actor_claim):
            raise BoardError("Huddle settlement requires a current participant")
        if h["state"] not in {"awaiting_scope", "open_round_1", "open_round_2"}:
            raise BoardError("Huddle requires lifecycle recovery before settlement")
        bids = {_claim_key(b["claim"]): b for b in h["bids"] if b["round"] == h["round"]}
        if now < _timestamp(h["reply_by"], "Huddle deadline") and len(bids) != len(h["claims"]):
            raise BoardError("Huddle settlement awaits bids or deadline")
        plans = {}
        plan_roots = {}
        for ref in h["claims"] + [b["support_claim"] for b in bids.values() if b["support_claim"]]:
            claim = current.get(_claim_key(ref))
            if claim is None or _claim_ref(claim) != ref or claim_is_stale(claim, now=now):
                raise BoardError("Huddle requires proof-first stale recovery before settlement")
            entity = next(e for e in payload["entities"] if e["id"] == ref["entity"])
            plan = Path(entity["plan"])
            if plan not in plans:
                plans[plan] = read_plan_bytes(plan)
                plan_roots[plan] = plan_state_token(plan)
            try:
                text = plans[plan].decode("utf-8")
            except UnicodeError:
                raise BoardError("Huddle settlement plan is not UTF-8") from None
            _huddle_checkpoint(text, ref["row"])
        yields = [b for b in bids.values() if b["role"] == "yield"]
        handoff = None
        if yields:
            if len(yields) != 1:
                raise BoardError("Huddle settlement requires exactly one handoff pair")
            offer = yields[0]
            target = bids.get(_claim_key(offer["target"]))
            if target is None or target["role"] != "own" or target["reason"] != "owner_authorized_handoff":
                raise BoardError("Huddle settlement requires a matching owner handoff pair")
            entity = next(e for e in payload["entities"] if e["id"] == offer["claim"]["entity"])
            if not is_local_plan(Path(entity["plan"]), home=home):
                raise BoardError("Huddle remote handoff requires authenticated two-phase recovery")
            handoff = dict(source_claim=offer["claim"], target_prior_claim=target["claim"],
                successor_claim={**offer["claim"], "owner": target["seat"]},
                target_prior_action="return_required", mode="local", remote_readback=None)
        _validate_bids(h, payload)
        old_generation = h["generation"]
        h["generation"] += 1
        payload["revision"] += 1
        if h["round"]:
            for ref in h["claims"]:
                key = _claim_key(ref)
                if key not in bids:
                    bid = dict(seat=ref["owner"], claim=copy.deepcopy(ref), role="unavailable",
                        scope=copy.deepcopy(current[key]["write_scope"]), reason="transport_unavailable",
                        target=None, support_claim=None, evidence={"kind": "none", "value": "self"},
                        round=h["round"], expected_huddle_generation=old_generation)
                    bid.update(bid_digest=_bid_digest(h["id"], bid), submitted_at=_stamp(now))
                    h["bids"].append(bid)
                    bids[key] = bid
        for key, bid in bids.items():
            if bid["role"] == "disjoint":
                current[key]["write_scope"] = copy.deepcopy(bid["scope"])
        semantic = {frozenset((_claim_key(e["left"]), _claim_key(e["right"])))
                    for e in h["edges"] if "semantic_suspicion" in e["kinds"]}
        edges = []
        for index, left in enumerate(h["claims"]):
            for right in h["claims"][index + 1:]:
                pair = (_claim_key(left), _claim_key(right))
                kinds = _scope_edge(current[pair[0]], current[pair[1]])
                if frozenset(pair) in semantic and not all(
                    key in bids and bids[key]["role"] == "disjoint"
                    and bids[key]["reason"] == "distinct_outcome" for key in pair):
                    kinds.append("semantic_suspicion")
                if kinds:
                    edges.append(dict(left=left, right=right, kinds=sorted(kinds)))
        h["edges"] = edges
        h["holds"] = claim_holds(h)
        held = {_claim_key(ref) for ref in h["holds"]}
        selected = [ref for ref in h["claims"] if _claim_key(ref) not in held]
        if handoff and (_claim_key(handoff["source_claim"]) in held
                        or _claim_key(handoff["target_prior_claim"]) not in held):
            raise BoardError("Huddle handoff must preserve selected-source and held-target authority")
        for bid in bids.values():
            if bid["support_claim"] is not None and any(
                _scope_edge(current[_claim_key(bid["support_claim"])], current[_claim_key(ref)])
                for ref in selected):
                raise BoardError("Huddle support scope conflicts with a selected writer")
        target_key = _claim_key(handoff["target_prior_claim"]) if handoff else None
        conflict = any(bids[key]["role"] in {"own", "disjoint"}
                       for key in held if key in bids and key != target_key)
        conflict = conflict or any("semantic_suspicion" in edge["kinds"]
            and not (handoff and { _claim_key(edge["left"]), _claim_key(edge["right"]) }
                     == {_claim_key(handoff["source_claim"]), target_key}) for edge in edges)
        if h["round"] == 1 and conflict:
            h.update(state="open_round_2", round=2, reply_by=_stamp(now + timedelta(minutes=2)))
            event = "round_opened"
        else:
            # Removing an edge cannot turn an explicit non-continuing bid
            # into permission to write. Its canonical return is still owed.
            held.update(key for key, bid in bids.items() if bid["role"] in {"stand_down", "review", "prove"})
            h["holds"] = [ref for ref in h["claims"] if _claim_key(ref) in held]
            selected = [ref for ref in h["claims"] if _claim_key(ref) not in held]
            rule = "owner_authorized_handoff" if handoff else "earliest_valid_claim" if edges or held else "path_disjoint"
            h["resolution"] = dict(settled_revision=payload["revision"], settled_at=_stamp(now),
                rule=rule, handoff=handoff,
                write_owners=[ref for ref in selected if current[_claim_key(ref)]["access"] == "write"],
                actions=[dict(claim=ref, action="return_required" if _claim_key(ref) in held
                              else "continue" if edges else "continue_disjoint") for ref in h["claims"]],
                support_actions=[dict(participant_claim=b["claim"], support_claim=b["support_claim"],
                                      action=b["role"] + "_claim") for b in bids.values() if b["support_claim"]])
            if handoff:
                source = handoff["source_claim"]
                h["resolution"]["write_owners"] = sorted(
                    [handoff["successor_claim"] if ref == source else ref
                     for ref in h["resolution"]["write_owners"]], key=_claim_rank)
                for action in h["resolution"]["actions"]:
                    if action["claim"] == source:
                        action["action"] = "handoff_complete"
                current[_claim_key(source)]["owner"] = handoff["successor_claim"]["owner"]
            entities = {e["id"]: e for e in payload["entities"]}
            h["compliance"] = [dict(claim=ref, required="canonical_disposition_then_return",
                plan_root_at_settlement=plan_roots[Path(entities[ref["entity"]]["plan"])],
                status="pending", completion=None) for ref in h["holds"]]
            h.update(state="awaiting_compliance" if held else "resolved", reply_by=None)
            if not held:
                h.update(resolved_at=_stamp(now), retain_until=_stamp(now + timedelta(hours=24)))
            event = "resolution_available"
        def guard():
            for plan, content in plans.items():
                if read_plan_bytes(plan) != content or plan_state_token(plan) != plan_roots[plan]:
                    raise BoardError("Huddle plan changed during settlement")
        _write_and_commit(root, path, payload, "shadow board: settle Huddle round", guard=guard, now=now)
        return BoardMutation(copy.deepcopy(payload), True, {
            "schema": "shadow.huddle-delivery-event.v1", "event": event,
            "huddle_id": h["id"], "generation": h["generation"]})


def preflight_access(*, entity: str, row: str, owner: str, repo: Path,
                     access: str, write_scope: list[str], expected_claim_revision: int | None,
                     expected_board_revision: int, now: datetime,
                     home: Path | None = None) -> BoardMutation:
    """Classify and open overlap atomically on an explicitly staged v2 board."""
    if type(expected_board_revision) is not int or type(expected_claim_revision) is not int:
        raise BoardError("preflight requires exact integer board and claim revisions")
    if access not in ("write", "read_only", "unscoped"):
        raise BoardError("preflight access is invalid")
    scope = normalize_write_scope(repo, write_scope)
    if (access == "write") != bool(scope):
        raise BoardError("only write access requires a nonempty scope")
    with _transaction(home) as (root, path, payload):
        if payload["schema"] != V2_SCHEMA:
            raise BoardError("automatic v2 activation is not available yet")
        if payload["revision"] != expected_board_revision:
            raise BoardError("preflight board revision changed")
        claim = next((c for c in payload["claims"] if (c["entity"], c["row"]) == (entity, row)), None)
        if claim is None or claim["claim_revision"] != expected_claim_revision:
            raise BoardError("preflight claim instance changed")
        if claim["owner"] != owner:
            raise AlreadyClaimed(claim["owner"])
        before = copy.deepcopy(claim)
        observed_binding = None if access == "read_only" else repository_binding(repo)
        binding = observed_binding
        if observed_binding is not None and claim["repository_binding"] is not None:
            if not _same_repository(observed_binding, claim["repository_binding"]):
                raise BoardError("preflight repository binding changed")
            binding = claim["repository_binding"]
        scope, component_witnesses = _scope_snapshot(repo, write_scope)
        if access == "write" and any(c is not claim and c["access"] == "unscoped" and c["repository_binding"] is None for c in payload["claims"]):
            raise BoardError("legacy_binding_unknown: classify or return every unbound legacy claim")
        involved = [h for h in payload["huddles"] if h["state"] != "resolved"
                    and (_claim_ref(claim) in h["claims"]
                         or h["resolution"] is not None and _claim_ref(claim) in h["resolution"]["write_owners"])]
        if involved and access == claim["access"] == "write" and scope == claim["write_scope"]:
            # Repeating an authorized scope does not advance a round or revoke
            # a selected writer. Each execution door still checks live holds.
            return BoardMutation(copy.deepcopy(payload), False, None)
        if involved:
            h = involved[0]
            if h["state"] not in ("awaiting_scope", "open_round_1", "open_round_2"):
                raise BoardError("Huddle requires lifecycle recovery before scope changes")
            if now >= _timestamp(h["reply_by"], "Huddle deadline"):
                raise BoardError("Huddle deadline reached; settle before scope changes")
            if h["state"] == "awaiting_scope" and claim["access"] != "unscoped":
                raise BoardError("only an unscoped owner may classify an awaiting-scope Huddle")
            if access == "read_only" and any("semantic_suspicion" in edge["kinds"]
                and _claim_ref(claim) in (edge["left"], edge["right"]) for edge in h["edges"]):
                raise BoardError("semantic suspicion requires paired distinct-outcome bids or return")
            if claim["access"] != "unscoped" and access != "write":
                raise BoardError("a Huddle source participant must return before dropping write access")
            if _claim_ref(claim) in h["holds"] and claim["access"] == "write":
                if access != "write" or any(not any(old == "." or p == old or p.startswith(old + "/")
                    for old in claim["write_scope"]) for p in scope):
                    raise BoardError("held claim cannot expand its scope or clear its hold through access changes")
        claim.update(access=access, write_scope=scope, repository_binding=binding)
        peers = [c for c in payload["claims"] if c is not claim and _scope_edge(claim, c)] if access != "read_only" else []
        huddle = None
        if peers or (involved and claim != before):
            reason = involved[0]["reason"] if involved else ("scope_request" if any(c["access"] == "unscoped" for c in [claim, *peers]) else "write_scope_overlap")
            huddle = _open_huddle(payload, claim, peers, reason, now, scope_changed=bool(involved and claim != before))
        if claim == before and huddle is None:
            return BoardMutation(copy.deepcopy(payload), False, None)
        payload["revision"] += 1
        def guard() -> None:
            if observed_binding is not None and repository_binding(repo) != observed_binding:
                raise BoardError("preflight repository changed during publication")
            if _scope_snapshot(repo, write_scope) != (scope, component_witnesses):
                raise BoardError("preflight scope component changed during publication")
        _write_and_commit(root, path, payload, "shadow board: preflight claim access", guard=guard, now=now)
        event = None if huddle is None else {"schema": "shadow.huddle-delivery-event.v1", "event": "huddle_changed",
            "huddle_id": huddle["id"], "generation": huddle["generation"]}
        return BoardMutation(copy.deepcopy(payload), True, event)


def authorize_host_attempt(*, context: dict | None, repo: Path, write_scope: list[str],
                           authority_proposal: bool, now: datetime,
                           home: Path | None = None) -> BoardMutation | None:
    """Preflight a host door, then recheck its exact claim before dispatch.

    V1 remains staged off. No-change proposals check ownership without changing
    access. The lock is released before the external worker runs; this is a
    cooperative launch authorization, not an operating-system write sandbox.
    """
    observed = snapshot(home=home)
    if observed is None or observed["schema"] == V1_SCHEMA:
        if context is not None:
            raise BoardError("host claim context requires a v2 board")
        return None
    if not isinstance(context, dict) or set(context) != {
        "entity", "row", "owner", "claim_revision", "board_revision"
    }:
        raise BoardError("host requires one complete exact claim context")
    if (not isinstance(context["entity"], str)
        or re.fullmatch(r"[0-9a-f]{64}", context["entity"]) is None
        or not isinstance(context["row"], str) or ROW_ID.fullmatch(context["row"]) is None
        or not isinstance(context["owner"], str) or not context["owner"]
        or len(context["owner"]) > 160
        or any(type(context[key]) is not int or context[key] < 0
               for key in ("claim_revision", "board_revision"))):
        raise BoardError("host claim context is malformed")
    scope, witnesses = _scope_snapshot(repo, write_scope)
    # Native editors do not promise no-follow operations on a terminal link.
    if any((repo / prefix).is_symlink() for prefix in scope):
        raise BoardError("host scope cannot dereference a terminal symlink")
    binding = repository_binding(repo)
    result = None
    revision = context["board_revision"]
    if not authority_proposal:
        result = preflight_access(
            entity=context["entity"], row=context["row"], owner=context["owner"],
            repo=repo, access="write", write_scope=write_scope,
            expected_claim_revision=context["claim_revision"],
            expected_board_revision=revision, now=now, home=home)
        revision = result.payload["revision"]
    with _transaction(home) as (_, _, payload):
        if payload["schema"] != V2_SCHEMA or payload["revision"] != revision:
            raise BoardError("host board changed; repeat preflight")
        claim = next((c for c in payload["claims"] if c["entity"] == context["entity"]
                      and c["row"] == context["row"]), None)
        if (claim is None or claim["owner"] != context["owner"]
            or claim["claim_revision"] != context["claim_revision"]):
            raise BoardError("host claim instance changed")
        if claim["repository_binding"] is None or not _same_repository(binding, claim["repository_binding"]):
            raise BoardError("host repository does not match the bound claim")
        if any(_claim_ref(claim) in h["holds"] for h in payload["huddles"] if h["state"] != "resolved"):
            raise BoardError("host claim is held; settle or return before launch")
        if repository_binding(repo) != binding or _scope_snapshot(repo, write_scope) != (scope, witnesses):
            raise BoardError("host repository or scope changed; repeat preflight")
        if any((repo / prefix).is_symlink() for prefix in scope):
            raise BoardError("host scope cannot dereference a terminal symlink")
        return result or BoardMutation(copy.deepcopy(payload), False, None)


def _rollback_v2_to_v1(
    home: Path,
    expected_revision: int,
    *,
    remote_parity: Callable[[dict], bool],
) -> dict:
    """Downgrade one empty v2 authority; retries against v1 are refused."""
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise BoardError("rollback expected revision must be an integer")
    if not callable(remote_parity):
        raise BoardError("rollback remote parity callback is required")
    with _transaction(home) as (root, path, payload):
        if payload["schema"] != V2_SCHEMA:
            raise BoardError("rollback requires an active v2 board")
        if payload["revision"] != expected_revision:
            raise BoardError("rollback revision does not match current authority")
        if payload["claims"]:
            raise BoardError("cannot downgrade a board with active claims")
        if payload["huddles"]:
            raise BoardError("cannot downgrade a board with Huddles")

        projection = {
            "schema": V1_SCHEMA,
            "revision": payload["revision"] + 1,
            "projects": copy.deepcopy(payload["projects"]),
            "entities": copy.deepcopy(payload["entities"]),
            "claims": [],
        }
        _validate_v1(projection)
        try:
            parity = remote_parity(copy.deepcopy(projection))
        except Exception as exc:
            raise BoardError("rollback remote parity could not be established") from exc
        if parity is not True:
            raise BoardError("rollback remote parity did not match local authority")

        _write_and_commit(
            root,
            path,
            projection,
            "shadow board: roll back v2 to v1",
        )
        try:
            raw = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_strict_json_object,
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise BoardError("rolled-back board is unreadable or malformed") from exc
        return copy.deepcopy(_validate_v1(raw))


def snapshot(*, home: Path | None = None) -> dict | None:
    root = _safe_root(home)
    git_dir = root / ".git"
    if git_dir.is_symlink() or (git_dir.exists() and not git_dir.is_dir()):
        raise BoardError("root board Git directory must not be a symlink or file")
    path = root / BOARD_NAME
    if path.is_file() or path.is_symlink():
        return _read(path)
    if (root / ".git").exists():
        raise BoardError("root board history exists but board.json is missing")
    return None


def board_file_sha256(*, home: Path | None = None) -> str:
    """Hash the exact canonical board bytes without exposing its private path."""
    path = _safe_root(home) / BOARD_NAME
    if not path.is_file() or path.is_symlink():
        raise BoardError("root board is missing, unreadable, or unsafe")
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise BoardError("root board could not be frozen") from exc


def board_authority_sha256(payload: dict) -> str:
    """Hash board authority while excluding only its monotonic revision."""
    validated = json.loads(json.dumps(_validate(payload)))
    validated.pop("revision")
    encoded = json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def seat_board_entities(
    payload: dict,
    seat: str,
    *,
    inspected_entities: set[str] | None = None,
) -> tuple[set[str], int]:
    """Return every locally owned entity or the next cold-seat board candidate."""
    seat = validate_owner(seat)
    inspected = set(inspected_entities or ())
    known = {entity["id"] for entity in payload["entities"]}
    if any(ENTITY_ID.fullmatch(identity) is None for identity in inspected):
        raise BoardError("inspected entities must be logical entity ids")
    if not inspected.issubset(known):
        raise BoardError("inspected entity is absent from this root board snapshot")
    owned = {
        claim["entity"]
        for claim in payload["claims"]
        if claim["owner"] == seat
    }
    if owned:
        return owned, len(owned)
    priorities = {
        project["id"]: project["priority"]
        for project in payload["projects"]
    }
    ordered = sorted(
        payload["entities"],
        key=lambda entity: (
            priorities[entity["project"]],
            entity["project"],
            entity["id"],
        ),
    )
    remaining = [
        entity for entity in ordered
        if entity["id"] not in inspected
    ]
    candidate = next(
        (entity for entity in remaining if entity["resume"] is not None),
        remaining[0] if remaining else None,
    )
    return ({candidate["id"]} if candidate is not None else set()), 0


def _identity_index(payload: dict) -> dict[str, list[dict]]:
    """Index live identities once; stored ids are fallback only for missing plans."""
    result: dict[str, list[dict]] = {}
    for entity in payload["entities"]:
        pointer = Path(entity["plan"])
        identity = entity_id(pointer) if regular_plan(pointer) else entity["id"]
        result.setdefault(identity, []).append(entity)
    return result


def registered_locator_index(*, home: Path | None = None) -> dict[str, tuple[Path, ...]]:
    """Current logical identities and every locator the board stores for each."""
    payload = snapshot(home=home)
    if payload is None:
        return {}
    return {
        identity: tuple(Path(entity["plan"]) for entity in entities)
        for identity, entities in _identity_index(payload).items()
    }


def _entity_aliases(payload: dict, plan: Path) -> list[dict]:
    """Every stored locator that currently resolves to one logical entity."""
    return _identity_index(payload).get(entity_id(plan), [])


def _entity_for(
    payload: dict,
    plan: Path,
    *,
    exact_on_conflict: bool = False,
) -> dict | None:
    """Resolve one entity; only return may address an exact alias to recover."""
    matches = _entity_aliases(payload, plan)
    if len(matches) > 1:
        if exact_on_conflict:
            candidate = str(plan.resolve())
            exact = [item for item in matches if item["plan"] == candidate]
            if len(exact) == 1:
                return exact[0]
        raise BoardError(
            "multiple registered entities now resolve to one Git identity; "
            "return one exact locator's claim, then run status to merge "
            "byte-identical aliases with disjoint rows"
        )
    if matches:
        return matches[0]
    return None


def entity_state(
    plan: Path,
    *,
    exact_on_conflict: bool = False,
    home: Path | None = None,
) -> dict | None:
    """Return the project grouping and exact entity addressed by one PLAN."""
    payload = snapshot(home=home)
    if payload is None:
        return None
    entity = _entity_for(payload, plan, exact_on_conflict=exact_on_conflict)
    return _state_for_entity(payload, entity)


def _state_for_entity(payload: dict, entity: dict | None) -> dict:
    """Copy one bounded entity view from an already validated snapshot."""
    if entity is None:
        return {
            "revision": payload["revision"],
            "project": None,
            "entity": None,
            "claims": [],
        }
    project = next(
        item for item in payload["projects"] if item["id"] == entity["project"]
    )
    return {
        "revision": payload["revision"],
        "project": json.loads(json.dumps(project)),
        "entity": json.loads(json.dumps(entity)),
        "claims": [
            json.loads(json.dumps(item))
            for item in payload["claims"]
            if item["entity"] == entity["id"]
        ],
    }




def _resolve_entity_payload(
    payload: dict,
    identity: str,
    *,
    revision: int | None = None,
) -> dict | None:
    """Resolve one entity from already validated board bytes."""
    if not isinstance(identity, str) or ENTITY_ID.fullmatch(identity) is None:
        raise BoardError("entity id must be one logical plan hash")
    if revision is not None and payload["revision"] != revision:
        raise BoardError("root board changed; refresh before writing")
    entity = next((item for item in payload["entities"] if item["id"] == identity), None)
    if entity is None:
        return {"state": _state_for_entity(payload, None), "plan": None}
    pointer = Path(entity["plan"])
    if not regular_plan(pointer):
        raise BoardError("registered entity plan is missing, unreadable, or a symlink")
    if entity_id(pointer) != identity:
        raise BoardError("entity id is stale; run shadow status to reconcile the board")
    aliases = _identity_index(payload).get(identity, [])
    if len(aliases) != 1 or aliases[0] is not entity:
        raise BoardError(
            "entity id has unresolved locator aliases; return conflicting exact claims, "
            "then run shadow status"
        )
    return {
        "state": _state_for_entity(payload, entity),
        "plan": pointer.resolve(),
    }


def resolve_entity(
    identity: str,
    *,
    revision: int | None = None,
    home: Path | None = None,
) -> dict | None:
    """Return one entity state and pointer from the same validated board snapshot."""
    payload = snapshot(home=home)
    if payload is None:
        return None
    return _resolve_entity_payload(payload, identity, revision=revision)


@contextmanager
def locked_entity_plan_by_id_at_revision(
    identity: str,
    *,
    revision: int,
    home: Path | None = None,
) -> Iterator[Path]:
    """Hold the board CAS while one bounded external receipt is written."""
    with _transaction(home) as (_, _, payload):
        resolved = _resolve_entity_payload(payload, identity, revision=revision)
        if resolved is None:
            raise BoardError("this computer has no Shadow board yet")
        if resolved["plan"] is None:
            raise BoardError("entity is not registered on this computer")
        yield resolved["plan"]




def canonical_plan_by_id_at_revision(
    identity: str,
    *,
    revision: int | None = None,
    home: Path | None = None,
) -> Path:
    """Resolve one current entity from one board snapshot, optionally as a CAS."""
    resolved = resolve_entity(identity, revision=revision, home=home)
    if resolved is None:
        raise BoardError("this computer has no Shadow board yet")
    if resolved["plan"] is None:
        raise BoardError("entity is not registered on this computer")
    return resolved["plan"]


def entity_integrity(
    entity: dict,
    claims: list[dict],
    row_ids: set[str],
    candidates: list[str],
) -> str | None:
    """One shared status/browser invariant for a board pointer and its rows."""
    missing = next((claim["row"] for claim in claims if claim["row"] not in row_ids), None)
    if missing is not None:
        return f"board claim {missing} is missing from the entity plan"
    if entity["resume"] is not None and entity["resume"] not in row_ids:
        return "the board resume is missing from the entity plan"
    claimed = {claim["row"] for claim in claims}
    if (
        entity["resume"] is not None
        and entity["resume"] not in claimed
        and entity["resume"] not in candidates
    ):
        return "the board resume is neither a live claim nor reachable work"
    if entity["resume"] is None and any(row not in claimed for row in candidates):
        return "the board has no resume for reachable work"
    return None


def _choose_resume(current: str | None, candidates: list[str], claimed: set[str]) -> str | None:
    """Use one resume law after reconcile, return, and crash recovery."""
    ordered = list(dict.fromkeys(candidates))
    if current in claimed and current in ordered:
        return current
    active = next((row for row in ordered if row in claimed), None)
    if active is not None:
        return active
    return next((row for row in ordered if row not in claimed), None)


def canonical_plan(
    plan: Path,
    *,
    repair_missing: bool = False,
    exact_on_conflict: bool = False,
    home: Path | None = None,
) -> Path:
    """Resolve a logical plan through the board without moving its pointer."""
    if not regular_plan(plan):
        raise BoardError("entity plan must be a regular, non-symlink PLAN.md")
    candidate = plan.resolve()
    state = entity_state(
        candidate,
        exact_on_conflict=exact_on_conflict,
        home=home,
    )
    if state is None or state["entity"] is None:
        return candidate
    stored_pointer = Path(state["entity"]["plan"])
    if not regular_plan(stored_pointer):
        if repair_missing and regular_plan(candidate):
            return candidate
        raise BoardError("stored canonical PLAN.md is missing or unreadable")
    return stored_pointer.resolve()


def _adopt_open_huddle_participant(payload: dict, old: dict, new: dict,
                                   now: datetime) -> dict | None:
    """Replace one expired identity without replaying its bids as new consent."""
    old_ref, new_ref = _claim_ref(old), _claim_ref(new)
    h = next((h for h in payload["huddles"]
              if h["state"] != "resolved" and old_ref in h["claims"]), None)
    if h is None:
        return None
    if h["state"] not in {"awaiting_scope", "open_round_1", "open_round_2"}:
        raise BoardError("Huddle adoption requires settled lifecycle recovery")
    h["claims"] = sorted((new_ref if ref == old_ref else ref for ref in h["claims"]), key=_claim_rank)
    for edge in h["edges"]:
        endpoints = sorted((new_ref if edge[end] == old_ref else edge[end]
                            for end in ("left", "right")), key=_claim_rank)
        edge["left"], edge["right"] = endpoints
    h["edges"].sort(key=lambda edge: (_claim_rank(edge["left"]), _claim_rank(edge["right"])))
    h["holds"] = claim_holds(h)
    h["bids"] = [bid for bid in h["bids"]
        if old_ref not in (bid["claim"], bid["target"], bid["support_claim"])
        and not (bid["round"] == h["round"] and bid["role"] == "yield"
                 and bid["claim"] in h["holds"])]
    h["generation"] += 1
    h["reply_by"] = _stamp(now + timedelta(minutes=2))
    return h


def claim(
    plan: Path,
    row: str,
    owner: str,
    *,
    project: str,
    priority: int,
    now: datetime | None = None,
    adopt_expired: bool = False,
    expected_plan: dict[str, str] | None = None,
    home: Path | None = None,
    repo: Path | None = None,
    access: str = "unscoped",
    write_scope: list[str] | None = None,
) -> dict:
    if not regular_plan(plan):
        raise BoardError("claim target must be a regular, non-symlink PLAN.md")
    plan = plan.resolve()
    if ROW_ID.fullmatch(row) is None:
        raise BoardError("claim target must carry one row id")
    if not isinstance(project, str) or PROJECT_ID.fullmatch(project) is None:
        raise BoardError("project must be a lowercase project slug")
    if isinstance(priority, bool) or priority not in range(1, 6):
        raise BoardError("project priority must be 1-5")
    owner = validate_owner(owner)
    claimed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    returned = claimed + timedelta(hours=DEFAULT_CLAIM_HOURS)
    if expected_plan is not None:
        preflight_plan, preflight_content = frozen_plan_snapshot(plan, home=home)
        if preflight_plan != expected_plan:
            raise BoardError("entity plan changed before the claim committed; retry")
    else:
        preflight_content = read_plan_bytes(plan)
    assert_hot_plan_budget(preflight_content)
    with _transaction(home) as (root, path, payload):
        if expected_plan is not None:
            observed, observed_content = frozen_plan_snapshot(plan, home=home)
            if observed != expected_plan:
                raise BoardError("entity plan changed before the claim committed; retry")
        else:
            observed_content = read_plan_bytes(plan)
        assert_hot_plan_budget(observed_content)
        entity = _entity_for(payload, plan)
        identity = entity["id"] if entity is not None else entity_id(plan)
        target = (identity, row)
        winner = next(
            (
                item
                for item in payload["claims"]
                if (item["entity"], item["row"]) == target
            ),
            None,
        )
        adoption_plan = None
        if winner is not None:
            if not adopt_expired or not claim_is_stale(winner, now=claimed):
                raise AlreadyClaimed(winner["owner"])
            if payload["schema"] == V2_SCHEMA:
                for h in _claim_huddles(payload, winner):
                    if h["state"] not in {"awaiting_scope", "open_round_1", "open_round_2"}:
                        raise BoardError("Huddle participant adoption requires settled lifecycle recovery")
                    adoption_plan = Path(entity["plan"])
                if any(b["support_claim"] == _claim_ref(winner)
                       for h in payload["huddles"] if h["state"] != "resolved" for b in h["bids"]):
                    raise BoardError("Huddle support claim must remain current until its participant returns")
                if ((access != "unscoped" and access != winner["access"])
                    or write_scope is not None and write_scope != winner["write_scope"]):
                    raise BoardError("stale adoption must preserve access and write scope")
                access, write_scope = winner["access"], copy.deepcopy(winner["write_scope"])
                if adoption_plan is not None:
                    adoption_bytes = read_plan_bytes(adoption_plan)
                    adoption_root = plan_state_token(adoption_plan)
                    try:
                        _huddle_checkpoint(adoption_bytes.decode("utf-8"), row)
                    except UnicodeError:
                        raise BoardError("Huddle adoption plan is not UTF-8") from None
            # Adoption is an explicit compare-and-swap under the same lock as
            # the fresh read.  It never silently reassigns a live claim.
            payload["claims"].remove(winner)
        binding = None
        observed_binding = None
        scope = [] if write_scope is None else write_scope
        component_witnesses = None
        if payload["schema"] == V2_SCHEMA:
            _enum(access, {"unscoped", "read_only", "write"}, "claim access")
            if not isinstance(scope, list):
                raise BoardError("claim write scope must be a bounded list")
            if (access == "write") != bool(scope):
                raise BoardError("only write access requires a nonempty scope")
            if access != "read_only":
                if repo is None:
                    raise BoardError("source claim requires an explicit repository")
                binding = observed_binding = repository_binding(repo)
                scope, component_witnesses = _scope_snapshot(repo, scope)
            if winner is not None:
                previous_binding = winner["repository_binding"]
                if ((binding is None) != (previous_binding is None)
                    or binding is not None and not _same_repository(binding, previous_binding)):
                    raise BoardError("stale adoption must preserve repository binding")
                binding = copy.deepcopy(previous_binding)
            if access == "write" and any(c["access"] == "unscoped" and c["repository_binding"] is None
                                         for c in payload["claims"]):
                raise BoardError("legacy_binding_unknown: classify or return every unbound legacy claim")
        elif access != "unscoped" or scope:
            raise BoardError("access declarations require an explicitly staged v2 board")
        grouping = next((item for item in payload["projects"] if item["id"] == project), None)
        if grouping is None:
            grouping = {
                "id": project,
                "priority": priority,
            }
            payload["projects"].append(grouping)
        if entity is None:
            entity = {
                "id": identity,
                "project": project,
                "plan": str(plan),
                "resume": row,
            }
            payload["entities"].append(entity)
        else:
            entity["resume"] = row
            if entity["project"] != project:
                entity["project"] = project
            if not regular_plan(Path(entity["plan"])):
                entity["plan"] = str(plan)
        claim_record = {
            "entity": identity,
            "row": row,
            "owner": owner,
            "claimed_at": _stamp(claimed),
            "return_by": _stamp(returned),
            "recovery": RECOVERY_ACTION,
        }
        if payload["schema"] == V2_SCHEMA:
            claim_record.update(claim_revision=payload["revision"] + 1, access=access,
                                repository_binding=binding, write_scope=scope)
        payload["claims"].append(claim_record)
        huddle = None
        if payload["schema"] == V2_SCHEMA and winner is not None:
            huddle = _adopt_open_huddle_participant(payload, winner, claim_record, claimed)
        if payload["schema"] == V2_SCHEMA and access != "read_only" and huddle is None:
            peers = [c for c in payload["claims"] if c is not claim_record and _scope_edge(claim_record, c)]
            if peers:
                reason = "scope_request" if any(c["access"] == "unscoped" for c in [claim_record, *peers]) else "write_scope_overlap"
                huddle = _open_huddle(payload, claim_record, peers, reason, claimed)
        payload["projects"].sort(key=lambda item: (item["priority"], item["id"]))
        payload["entities"].sort(key=lambda item: (item["project"], item["id"]))
        payload["claims"].sort(key=lambda item: (item["entity"], item["row"]))
        payload["revision"] += 1
        def guard() -> None:
            if adoption_plan is not None and (read_plan_bytes(adoption_plan) != adoption_bytes
                or plan_state_token(adoption_plan) != adoption_root):
                raise BoardError("canonical plan changed during stale adoption")
            if binding is not None and (repository_binding(repo) != observed_binding
                or _scope_snapshot(repo, scope) != (scope, component_witnesses)):
                raise BoardError("claim repository or scope changed during publication")
        _write_and_commit(root, path, payload, f"shadow board: claim {row}", guard=guard, now=claimed)
        snapshot = json.loads(json.dumps(payload))
        result = {
            "payload": snapshot,
            "entity": next(item for item in snapshot["entities"] if item["id"] == identity),
            "claim": next(
                item
                for item in snapshot["claims"]
                if (item["entity"], item["row"], item["owner"])
                == (identity, row, owner)
            ),
        }
        if payload["schema"] == V2_SCHEMA:
            result["event"] = None if huddle is None else {
                "schema": "shadow.huddle-delivery-event.v1", "event": "huddle_changed",
                "huddle_id": huddle["id"], "generation": huddle["generation"],
            }
        return result


def complete_init_registration(
    entity: dict,
    receipt: bytes,
    repository_witness: Callable[[], bool],
    *,
    home: Path | None = None,
) -> dict:
    """Consume one exact init receipt while registering at most one entity."""
    plan = Path(entity.get("plan", ""))
    return reconcile(
        [entity],
        [],
        home=home,
        _init_registration=(plan, receipt, repository_witness),
    )


def _init_registration_ref(plan: Path) -> str:
    locator = str(Path(os.path.abspath(plan)))
    digest = hashlib.sha256(locator.encode("utf-8")).hexdigest()
    return f"{INIT_REGISTRATION_REF_PREFIX}/{digest}"


def _init_registration_oid(root: Path, reference: str) -> str | None:
    symbolic = _git(root, "symbolic-ref", "--quiet", reference)
    if symbolic.returncode == 0:
        raise BoardError("init registration receipt ref is symbolic")
    if symbolic.returncode != 1:
        raise BoardError("init registration receipt ref could not be inspected")
    current = _git(root, "rev-parse", "--verify", "--quiet", reference)
    if current.returncode == 1:
        return None
    if current.returncode or not GIT_OBJECT_ID.fullmatch(current.stdout.strip()):
        raise BoardError("init registration receipt ref is malformed")
    oid = current.stdout.strip()
    kind = _git(root, "cat-file", "-t", oid)
    if kind.returncode or kind.stdout.strip() != "blob":
        raise BoardError("init registration receipt ref does not name a blob")
    return oid


def _read_init_registration_blob(root: Path, oid: str) -> bytes:
    measured = _git(root, "cat-file", "-s", oid)
    try:
        size = int(measured.stdout.strip())
    except ValueError as exc:
        raise BoardError("init registration receipt size could not be read") from exc
    if (
        measured.returncode
        or size < 1
        or size > MAX_INIT_REGISTRATION_RECEIPT_BYTES
    ):
        raise BoardError("init registration receipt is missing or oversized")
    content = _git_bytes(root, "cat-file", "blob", oid)
    if content.returncode or len(content.stdout) != size:
        raise BoardError("init registration receipt could not be read")
    return content.stdout


def _required_init_registration_oid(
    root: Path,
    reference: str,
    receipt: bytes,
) -> str:
    expected = _git_bytes(root, "hash-object", "--stdin", content=receipt)
    oid = expected.stdout.decode("ascii", errors="ignore").strip()
    if expected.returncode or GIT_OBJECT_ID.fullmatch(oid) is None:
        raise BoardError("init registration receipt could not be identified")
    current = _init_registration_oid(root, reference)
    if (
        current != oid
        or _read_init_registration_blob(root, oid) != receipt
    ):
        raise BoardError("init registration receipt changed before registration")
    return oid


def _clear_init_registration_locked(
    root: Path,
    reference: str,
    receipt: bytes,
    *,
    missing_ok: bool,
) -> None:
    current = _init_registration_oid(root, reference)
    if current is None:
        if missing_ok:
            return
        raise BoardError("init registration receipt is missing")
    oid = _required_init_registration_oid(root, reference, receipt)
    deleted = _git(
        root,
        "update-ref",
        "-m",
        "shadow init: complete registration",
        "--no-deref",
        "-d",
        reference,
        oid,
    )
    if deleted.returncode or _init_registration_oid(root, reference) is not None:
        raise BoardError("init registration receipt could not be completed")


def read_init_registration(
    plan: Path,
    *,
    home: Path | None = None,
) -> bytes | None:
    """Read one pending init receipt without creating board authority."""
    root = _safe_root(home)
    git_dir = root / ".git"
    if not git_dir.exists():
        return None
    if git_dir.is_symlink() or not git_dir.is_dir():
        raise BoardError("root board Git directory must not be a symlink or file")
    reference = _init_registration_ref(plan)
    with _transaction(home) as (locked_root, _, _):
        oid = _init_registration_oid(locked_root, reference)
        return (
            _read_init_registration_blob(locked_root, oid)
            if oid is not None
            else None
        )


def prepare_init_registration(
    plan: Path,
    receipt: bytes,
    *,
    home: Path | None = None,
) -> bytes:
    """CAS-create or resume one pending init receipt in the board journal."""
    if not isinstance(receipt, bytes) or not (
        1 <= len(receipt) <= MAX_INIT_REGISTRATION_RECEIPT_BYTES
    ):
        raise BoardError("init registration receipt is empty or oversized")
    reference = _init_registration_ref(plan)
    with _transaction(home) as (root, _, _):
        current = _init_registration_oid(root, reference)
        if current is not None:
            return _read_init_registration_blob(root, current)
        stored = _git_bytes(root, "hash-object", "-w", "--stdin", content=receipt)
        oid = stored.stdout.decode("ascii", errors="ignore").strip()
        if stored.returncode or not GIT_OBJECT_ID.fullmatch(oid):
            raise BoardError("init registration receipt could not be stored")
        created = _git(
            root,
            "update-ref",
            "-m",
            "shadow init: reserve registration",
            "--no-deref",
            reference,
            oid,
            "0" * len(oid),
        )
        if created.returncode:
            raise BoardError("init registration receipt could not be reserved")
        confirmed = _init_registration_oid(root, reference)
        if confirmed != oid or _read_init_registration_blob(root, oid) != receipt:
            raise BoardError("init registration receipt reservation changed")
        return receipt


def reconcile(
    entities: list[dict],
    legacy_claims: list[dict],
    *,
    retired_entities: list[str] | None = None,
    retired_sources: list[dict] | None = None,
    home: Path | None = None,
    _init_registration: tuple[Path, bytes, Callable[[], bool]] | None = None,
) -> dict:
    """Atomically import bounded discovery into pointer-only local authority.

    Discovery may add an entity or repair a missing locator. It never replaces
    a healthy canonical locator, project priority, or that entity's resume with
    metadata from a sibling checkout. Historical plan claims are consumed once.
    """
    if _init_registration is not None and (
        len(entities) != 1
        or legacy_claims
        or retired_entities
        or retired_sources
    ):
        raise BoardError("new entity registration requires one live entity seed")
    if _init_registration is not None:
        registration_plan, registration_receipt, repository_witness = (
            _init_registration
        )
        if (
            not isinstance(registration_plan, Path)
            or not isinstance(registration_receipt, bytes)
            or not 1
            <= len(registration_receipt)
            <= MAX_INIT_REGISTRATION_RECEIPT_BYTES
            or not callable(repository_witness)
        ):
            raise BoardError("init registration completion input is invalid")
        registration_plan = Path(os.path.abspath(registration_plan))
        registration_reference = _init_registration_ref(registration_plan)
    else:
        registration_plan = None
        registration_receipt = None
        repository_witness = None
        registration_reference = None
    retired_ids = set(retired_entities or [])
    if any(
        not isinstance(identity, str) or ENTITY_ID.fullmatch(identity) is None
        for identity in retired_ids
    ):
        raise BoardError("retired entities must be logical entity ids")
    prepared_retired: list[dict] = []
    for source in retired_sources or []:
        identity = source.get("identity")
        plan = source.get("plan")
        expected_state = source.get("expected_state")
        registered_plan = source.get("registered_plan")
        witnesses = source.get("witnesses") or []
        if identity not in retired_ids:
            raise BoardError("retired source must name a retired entity")
        if not isinstance(plan, str) or not Path(plan).is_absolute():
            raise BoardError("retired source must name an absolute plan locator")
        if (
            not isinstance(expected_state, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_state) is None
        ):
            raise BoardError("retired source content token is invalid")
        if registered_plan is not None and (
            not isinstance(registered_plan, str) or not Path(registered_plan).is_absolute()
        ):
            raise BoardError("retired registered locator predicate is invalid")
        # A retirement is decided by the whole set of same-identity copies:
        # the demotion retires the entity only because no strictly newer copy
        # declined to repeat it. So every copy the verdict read is a predicate
        # of the transaction, and each carries its own bounded state token.
        if not isinstance(witnesses, list) or len(witnesses) > MAX_DISCOVERY_WITNESSES:
            raise BoardError("retired source witnesses are invalid")
        prepared_witnesses: list[dict] = []
        for witness in witnesses:
            if not isinstance(witness, dict):
                raise BoardError("retired source witnesses are invalid")
            witness_plan = witness.get("plan")
            witness_state = witness.get("expected_state")
            if not isinstance(witness_plan, str) or not Path(witness_plan).is_absolute():
                raise BoardError("retired source witness must name an absolute plan locator")
            if (
                not isinstance(witness_state, str)
                or re.fullmatch(r"[0-9a-f]{64}", witness_state) is None
            ):
                raise BoardError("retired source witness content token is invalid")
            prepared_witnesses.append(
                {"plan": witness_plan, "expected_state": witness_state}
            )
        if not any(witness["plan"] == plan for witness in prepared_witnesses):
            prepared_witnesses.append({"plan": plan, "expected_state": expected_state})
        prepared_retired.append(
            {
                "identity": identity,
                "plan": plan,
                "expected_state": expected_state,
                "registered_plan": registered_plan,
                "witnesses": prepared_witnesses,
            }
        )
    if (
        len(prepared_retired) != len(retired_ids)
        or {source["identity"] for source in prepared_retired} != retired_ids
    ):
        raise BoardError("every retired entity must carry one bounded source token")
    prepared: list[dict] = []
    for seed in entities:
        source = Path(seed.get("plan", ""))
        project = seed.get("project")
        priority = seed.get("priority")
        candidates = seed.get("candidates")
        rows = seed.get("rows", candidates)
        expected_identity = seed.get("identity")
        expected_size = seed.get("expected_size")
        expected_sha256 = seed.get("expected_sha256")
        repair_from = seed.get("repair_from")
        repair_state = seed.get("repair_state")
        registered_plan = seed.get("registered_plan")
        witnesses = seed.get("witnesses") or []
        if not regular_plan(source):
            raise BoardError("import entity must point to a regular, non-symlink PLAN.md")
        plan = source.resolve()
        if not isinstance(project, str) or PROJECT_ID.fullmatch(project) is None:
            raise BoardError("import project must be a lowercase project slug")
        if isinstance(priority, bool) or priority not in range(1, 6):
            raise BoardError("import project priority must be 1-5")
        if not isinstance(candidates, list) or any(
            not isinstance(row, str) or ROW_ID.fullmatch(row) is None
            for row in candidates
        ):
            raise BoardError("import candidates must be row ids")
        if not isinstance(rows, list) or any(
            not isinstance(row, str) or ROW_ID.fullmatch(row) is None
            for row in rows
        ):
            raise BoardError("import rows must be row ids")
        if not set(candidates).issubset(rows):
            raise BoardError("import candidates must also be import rows")
        identity = entity_id(plan)
        if expected_identity is not None and (
            not isinstance(expected_identity, str)
            or ENTITY_ID.fullmatch(expected_identity) is None
            or expected_identity != identity
        ):
            raise BoardError("bounded discovery entity identity changed before reconciliation")
        if (expected_size is None) != (expected_sha256 is None):
            raise BoardError("bounded discovery content token is incomplete")
        if expected_size is not None and (
            isinstance(expected_size, bool)
            or not isinstance(expected_size, int)
            or expected_size < 0
            or expected_size > MAX_PLAN_BYTES
            or not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        ):
            raise BoardError("bounded discovery content token is invalid")
        locator_fields: dict[str, str | None] = {}
        for name, value in (
            ("repair_from", repair_from),
            ("registered_plan", registered_plan),
        ):
            if value is not None:
                if not isinstance(value, str) or not Path(value).is_absolute():
                    raise BoardError("bounded discovery locator predicate is invalid")
                locator_fields[name] = str(Path(value))
            else:
                locator_fields[name] = None
        if repair_from is not None and registered_plan is not None:
            raise BoardError("bounded discovery locator predicates conflict")
        if repair_from is None:
            if repair_state is not None:
                raise BoardError("bounded discovery repair token has no locator")
        elif (
            not isinstance(repair_state, str)
            or (
                repair_state != "unavailable"
                and re.fullmatch(r"[0-9a-f]{64}", repair_state) is None
            )
        ):
            raise BoardError("bounded discovery repair token is invalid")
        if not isinstance(witnesses, list) or len(witnesses) > MAX_DISCOVERY_WITNESSES:
            raise BoardError("bounded discovery witnesses are invalid")
        prepared_witnesses: list[dict] = []
        for witness in witnesses:
            if not isinstance(witness, dict):
                raise BoardError("bounded discovery witnesses are invalid")
            witness_plan = witness.get("plan")
            witness_state = witness.get("expected_state")
            if not isinstance(witness_plan, str) or not Path(witness_plan).is_absolute():
                raise BoardError(
                    "bounded discovery witness must name an absolute plan locator"
                )
            if (
                not isinstance(witness_state, str)
                or re.fullmatch(r"[0-9a-f]{64}", witness_state) is None
            ):
                raise BoardError("bounded discovery witness content token is invalid")
            prepared_witnesses.append(
                {"plan": witness_plan, "expected_state": witness_state}
            )
        prepared.append(
            {
                "id": identity,
                "project": project,
                "plan": str(plan),
                "priority": priority,
                "candidates": list(dict.fromkeys(candidates)),
                "rows": list(dict.fromkeys(rows)),
                "expected_size": expected_size,
                "expected_sha256": expected_sha256,
                "repair_state": repair_state,
                "witnesses": prepared_witnesses,
                **locator_fields,
            }
        )
    if (
        registration_plan is not None
        and prepared[0]["plan"] != str(registration_plan.resolve())
    ):
        raise BoardError("init registration plan changed before completion")

    def assert_repository_witness() -> None:
        if repository_witness is None:
            return
        try:
            matches = repository_witness()
        except Exception as exc:
            raise BoardError(
                "init registration repository identity could not be verified"
            ) from exc
        if matches is not True:
            raise BoardError(
                "init registration repository identity changed before registration"
            )

    def assert_init_registration(root: Path) -> str | None:
        if registration_reference is None or registration_receipt is None:
            return None
        assert_repository_witness()
        return _required_init_registration_oid(
            root,
            registration_reference,
            registration_receipt,
        )

    seed_ids = [seed["id"] for seed in prepared]
    duplicated = {identity for identity in seed_ids if seed_ids.count(identity) > 1}
    if duplicated:
        # Name the colliding seeds: a reader spent a day on the bare message
        # (2026-08-18) because it could not say WHICH two paths one identity
        # arrived from.
        colliding = ", ".join(
            seed["plan"] for seed in prepared if seed["id"] in duplicated
        )
        raise BoardError(
            f"bounded discovery returned a duplicate logical entity: {colliding}"
        )
    if retired_ids.intersection(seed["id"] for seed in prepared):
        raise BoardError("bounded discovery marked one entity both live and retired")

    def assert_seed_content() -> None:
        for seed in prepared:
            try:
                content = read_plan_bytes(Path(seed["plan"]))
            except BoardError as exc:
                # A quarantined seed declares its plan unreadable with None
                # markers; reconcile must tolerate exactly that, never demand
                # a successful read of the file discovery already quarantined.
                if seed["expected_sha256"] is not None:
                    raise BoardError(
                        "bounded discovery entity changed during reconciliation; retry"
                    ) from exc
                continue
            try:
                assert_hot_plan_budget(content)
            except BoardError:
                # Quarantine, never blank the board: the entity registers
                # unhealthy and every claim and plan-write path still
                # enforces the budget at its own gate.
                # Constant text only: the scanner treats seed-derived values
                # as sensitive, and status names the broken plan regardless.
                print(
                    "shadow: one local plan enters the board over its "
                    "hot-plan budget; shadow status names it as broken",
                    file=sys.stderr,
                )
            if seed["expected_size"] is not None and (
                len(content) != seed["expected_size"]
                or hashlib.sha256(content).hexdigest() != seed["expected_sha256"]
            ):
                raise BoardError(
                    "bounded discovery entity changed during reconciliation; retry"
                )
            if entity_id(Path(seed["plan"])) != seed["id"]:
                raise BoardError(
                    "bounded discovery entity identity changed during reconciliation; retry"
                )

    def assert_repair_states() -> None:
        for seed in prepared:
            if seed["repair_from"] is None:
                continue
            if plan_state_token(Path(seed["repair_from"])) != seed["repair_state"]:
                raise BoardError(
                    "registered board locator changed during reconciliation; retry"
                )

    def assert_seed_witnesses() -> None:
        for seed in prepared:
            for witness in seed["witnesses"]:
                try:
                    state = plan_state_token(Path(witness["plan"]))
                except BoardError as exc:
                    raise BoardError(
                        "bounded discovery comparison changed during reconciliation; retry"
                    ) from exc
                if state != witness["expected_state"]:
                    raise BoardError(
                        "bounded discovery comparison changed during reconciliation; retry"
                    )

    def assert_retired_content() -> None:
        for source in prepared_retired:
            try:
                pointer = Path(source["plan"])
                state = plan_state_token(pointer)
                identity = entity_id(pointer)
            except BoardError as exc:
                raise BoardError(
                    "self-demotion source changed during reconciliation; retry"
                ) from exc
            if (
                state != source["expected_state"]
                or identity != source["identity"]
            ):
                raise BoardError(
                    "self-demotion source changed during reconciliation; retry"
                )
            # The other copies are checked by state alone. Their identity is
            # not re-derived: a nested declared plan legitimately reports a
            # different `entity_id` than the logical key it belongs to, and
            # only "did this copy change since the verdict read it" is being
            # asked of them.
            for witness in source["witnesses"]:
                if witness["plan"] == source["plan"]:
                    continue
                if plan_state_token(Path(witness["plan"])) != witness["expected_state"]:
                    raise BoardError(
                        "self-demotion source changed during reconciliation; retry"
                    )

    assert_seed_content()
    assert_repair_states()
    assert_seed_witnesses()
    assert_retired_content()
    with _transaction(home) as (root, path, payload):
        registration_oid = assert_init_registration(root)
        assert_seed_content()
        assert_repair_states()
        assert_seed_witnesses()
        assert_retired_content()
        original_payload = json.loads(json.dumps(payload))
        identity_index = _identity_index(payload)
        if registration_reference is not None and prepared[0]["id"] in identity_index:
            exact = [
                entity
                for entity in identity_index[prepared[0]["id"]]
                if entity["plan"] == prepared[0]["plan"]
            ]
            if len(exact) != 1:
                raise BoardError("entity is already registered on this computer")
            registration_oid = assert_init_registration(root)
            assert_seed_content()
            assert_seed_witnesses()
            _clear_init_registration_locked(
                root,
                registration_reference,
                registration_receipt,
                missing_ok=False,
            )
            try:
                assert_repository_witness()
                assert_seed_content()
                assert_seed_witnesses()
            except BaseException:
                restored = _git(
                    root,
                    "update-ref",
                    "-m",
                    "shadow init: restore incomplete registration",
                    "--no-deref",
                    registration_reference,
                    registration_oid,
                    "0" * len(registration_oid),
                )
                if (
                    restored.returncode
                    or _init_registration_oid(root, registration_reference)
                    != registration_oid
                ):
                    raise BoardError(
                        "init registration cleanup failed and its receipt "
                        "could not be restored"
                    )
                raise
            return json.loads(json.dumps(payload))
        prepared_by_id = {seed["id"]: seed for seed in prepared}
        original_claims = json.loads(json.dumps(payload["claims"]))

        for seed in prepared:
            expected_locator = seed["registered_plan"] or seed["repair_from"]
            if expected_locator is None:
                continue
            aliases = identity_index.get(seed["id"], [])
            if len(aliases) != 1 or aliases[0]["plan"] != expected_locator:
                raise BoardError(
                    "registered board locator changed during reconciliation; retry"
                )
        for source in prepared_retired:
            expected_locator = source["registered_plan"]
            if expected_locator is None:
                continue
            aliases = identity_index.get(source["identity"], [])
            if not any(alias["plan"] == expected_locator for alias in aliases):
                raise BoardError(
                    "registered board locator changed during reconciliation; retry"
                )

        # Work out every identity transition against immutable old ids, then
        # replace entities and claims once. Incremental id mutation is unsafe:
        # in a cycle such as A+B -> C while C -> A, a string-id delete/rekey can
        # steal C's claims or delete its entity before the merge finishes.
        final_entities: list[dict] = []
        old_to_final: dict[str, str] = {}
        retired_old_ids: set[str] = set()
        new_ids: set[str] = set()
        priorities: dict[str, int] = {}
        for seed in prepared:
            priorities[seed["project"]] = min(
                priorities.get(seed["project"], seed["priority"]),
                seed["priority"],
            )
        project_by_id = {project["id"]: project for project in payload["projects"]}
        for slug, priority in priorities.items():
            if slug not in project_by_id:
                grouping = {"id": slug, "priority": priority}
                payload["projects"].append(grouping)
                project_by_id[slug] = grouping

        for identity, aliases in identity_index.items():
            if identity in retired_ids:
                retired_old_ids.update(alias["id"] for alias in aliases)
                continue
            seed = prepared_by_id.get(identity)
            if len(aliases) > 1:
                if seed is None:
                    for alias in aliases:
                        final_entities.append(json.loads(json.dumps(alias)))
                        old_to_final[alias["id"]] = alias["id"]
                    continue
                alias_ids = {alias["id"] for alias in aliases}
                alias_claims = [
                    claim for claim in original_claims
                    if claim["entity"] in alias_ids
                ]
                rows: dict[str, list[str]] = {}
                for claim in alias_claims:
                    rows.setdefault(claim["row"], []).append(claim["owner"])
                duplicate = next(
                    ((row, owners) for row, owners in rows.items() if len(owners) > 1),
                    None,
                )
                if duplicate is not None:
                    row, owners = duplicate
                    raise BoardError(
                        f"entity aliases both claim {row} by {', '.join(sorted(owners))}; "
                        "return one exact locator before convergence"
                    )
                seed_bytes = read_plan_bytes(Path(seed["plan"]))
                for alias in aliases:
                    pointer = Path(alias["plan"])
                    owned = [claim for claim in alias_claims if claim["entity"] == alias["id"]]
                    if not regular_plan(pointer):
                        if alias["resume"] is not None or owned:
                            raise BoardError(
                                "a missing entity alias still owns resume or claim state; "
                                "restore that exact plan before convergence"
                            )
                        continue
                    if read_plan_bytes(pointer) != seed_bytes:
                        raise BoardError(
                            "entity aliases have divergent PLAN.md bytes; converge the "
                            "plans before their board identities can merge"
                        )
                    if alias["resume"] is not None and alias["resume"] not in seed["candidates"]:
                        raise BoardError(
                            f"entity alias resume {alias['resume']} is absent from the converged plan"
                        )
                absent_claim = next(
                    (claim for claim in alias_claims if claim["row"] not in seed["candidates"]),
                    None,
                )
                if absent_claim is not None:
                    raise BoardError(
                        f"entity alias claim {absent_claim['row']} is absent from the converged plan"
                    )
                source = next(
                    (alias for alias in aliases if alias["id"] == seed["id"]),
                    next(
                        (alias for alias in aliases if alias["plan"] == seed["plan"]),
                        min(aliases, key=lambda alias: alias["id"]),
                    ),
                )
                entity = json.loads(json.dumps(source))
                survivor = identity
                for alias in aliases:
                    old_to_final[alias["id"]] = survivor
                entity["id"] = survivor
                entity["plan"] = seed["plan"]
                entity["project"] = seed["project"]
                claimed_rows = {claim["row"] for claim in alias_claims}
                entity["resume"] = next(
                    (row for row in seed["candidates"] if row in claimed_rows),
                    next(iter(seed["candidates"]), None),
                )
                final_entities.append(entity)
                seed["refresh"] = True
                seed["resolved_id"] = survivor
                continue
            source = aliases[0]
            entity = json.loads(json.dumps(source))
            old_to_final[source["id"]] = identity
            entity["id"] = identity
            if seed is not None:
                should_repair = seed["repair_from"] is not None
                if entity["plan"] != seed["plan"] and (
                    not regular_plan(Path(entity["plan"])) or should_repair
                ):
                    owned_rows = {
                        claim["row"]
                        for claim in original_claims
                        if claim["entity"] == source["id"]
                    }
                    missing = sorted(owned_rows.difference(seed["rows"]))
                    if missing:
                        raise BoardError(
                            f"repaired entity plan is missing claimed row {missing[0]}"
                        )
                    if entity["resume"] is not None and entity["resume"] not in seed["rows"]:
                        raise BoardError(
                            f"repaired entity plan is missing resume {entity['resume']}"
                        )
                    entity["plan"] = seed["plan"]
                    seed["refresh"] = True
                else:
                    # A healthy stored locator remains canonical. Candidate rows
                    # parsed from another checkout cannot move its resume.
                    seed["refresh"] = entity["plan"] == seed["plan"]
                if entity["project"] != seed["project"] and seed["refresh"]:
                    entity["project"] = seed["project"]
                seed["resolved_id"] = identity
            final_entities.append(entity)

        for seed in prepared:
            if seed["id"] in identity_index:
                continue
            if any(entity["id"] == seed["id"] for entity in final_entities):
                raise BoardError(
                    "a stale stored entity id blocks this live identity; reconcile the "
                    "full portfolio before registering it"
                )
            entity = {
                "id": seed["id"],
                "project": seed["project"],
                "plan": seed["plan"],
                "resume": None,
            }
            final_entities.append(entity)
            new_ids.add(entity["id"])
            seed["refresh"] = True
            seed["resolved_id"] = entity["id"]

        final_ids = [entity["id"] for entity in final_entities]
        if len(final_ids) != len(set(final_ids)):
            raise BoardError(
                "live entity identities collide with unresolved aliases; reconcile the "
                "full portfolio before using a narrower import root"
            )
        final_claims: list[dict] = []
        targets: dict[tuple[str, str], list[str]] = {}
        for old_claim in original_claims:
            if old_claim["entity"] in retired_old_ids:
                continue
            claim = json.loads(json.dumps(old_claim))
            claim["entity"] = old_to_final[old_claim["entity"]]
            target = (claim["entity"], claim["row"])
            targets.setdefault(target, []).append(claim["owner"])
            final_claims.append(claim)
        conflict = next(
            ((target, owners) for target, owners in targets.items() if len(owners) > 1),
            None,
        )
        if conflict is not None:
            (_, row), owners = conflict
            raise BoardError(
                f"entity aliases both claim {row} by {', '.join(sorted(owners))}; "
                "return one exact locator before convergence"
            )
        payload["entities"] = final_entities
        payload["claims"] = final_claims
        by_id = {entity["id"]: entity for entity in payload["entities"]}

        import_ids = new_ids
        if import_ids:
            for historical in legacy_claims:
                plan = Path(historical.get("plan", "")).resolve()
                entity = _entity_for(payload, plan)
                identity = entity["id"] if entity is not None else entity_id(plan)
                row = historical.get("row")
                owner = historical.get("owner") or "another seat"
                claimed_at = _timestamp(historical.get("claimed_at"), "legacy claim time")
                target = (identity, row)
                if identity not in by_id or ROW_ID.fullmatch(str(row)) is None:
                    raise BoardError("legacy claim points outside bounded discovery")
                if identity not in import_ids:
                    continue
                if any(
                    (claim["entity"], claim["row"]) == target
                    for claim in payload["claims"]
                ):
                    continue
                imported_claim = {
                    "entity": identity,
                    "row": row,
                    "owner": owner,
                    "claimed_at": _stamp(claimed_at),
                    "return_by": _stamp(
                        claimed_at + timedelta(hours=DEFAULT_CLAIM_HOURS)
                    ),
                    "recovery": RECOVERY_ACTION,
                }
                if payload["schema"] == V2_SCHEMA:
                    imported_claim.update(claim_revision=0, access="unscoped",
                                          repository_binding=None, write_scope=[])
                payload["claims"].append(imported_claim)
        claims_by_entity: dict[str, set[str]] = {}
        for item in payload["claims"]:
            claims_by_entity.setdefault(item["entity"], set()).add(item["row"])
        for seed in prepared:
            if not seed["refresh"]:
                continue
            entity = by_id[seed["resolved_id"]]
            claimed = claims_by_entity.get(entity["id"], set())
            resume = (
                entity["resume"]
                if seed["repair_from"] is not None
                and entity["resume"] in seed["candidates"]
                else _choose_resume(entity["resume"], seed["candidates"], claimed)
            )
            if entity["resume"] != resume:
                entity["resume"] = resume

        used_projects = {entity["project"] for entity in payload["entities"]}
        if any(project["id"] not in used_projects for project in payload["projects"]):
            payload["projects"] = [
                project for project in payload["projects"] if project["id"] in used_projects
            ]

        payload["projects"].sort(key=lambda item: (item["priority"], item["id"]))
        payload["entities"].sort(key=lambda item: (item["project"], item["id"]))
        payload["claims"].sort(key=lambda item: (item["entity"], item["row"]))
        _refresh_repository_identity_cache()
        assert_seed_content()
        assert_repair_states()
        assert_seed_witnesses()
        assert_retired_content()
        if payload == original_payload:
            return json.loads(json.dumps(payload))
        payload["revision"] = original_payload["revision"] + 1
        _validate(payload)
        if registration_reference is None:
            _write_and_commit(
                root,
                path,
                payload,
                "shadow board: reconcile bounded portfolio",
            )
        else:
            registration_oid = assert_init_registration(root)

            def registration_guard() -> None:
                assert_repository_witness()
                assert_seed_content()
                assert_seed_witnesses()

            _write_and_commit(
                root,
                path,
                payload,
                "shadow board: register initialized plan",
                consume_ref=(registration_reference, registration_oid),
                guard=registration_guard,
            )
        return json.loads(json.dumps(payload))


def _release_state(plan: Path, row: str, reason: str, *, text: str | None = None) -> None:
    if text is None:
        try:
            text = read_plan_text(plan)
        except BoardError as exc:
            raise BoardError("claim return needs a readable entity plan") from exc
    row_matches = []
    for line in text.splitlines():
        match = _grammar.ROW_RE.match(line)
        if match is not None and match.group("id") == row:
            row_matches.append(match)
    if not row_matches:
        if reason == "orphan":
            return
        raise BoardError("claim return row is missing from the entity plan")
    if len(row_matches) != 1:
        raise BoardError("claim return row id is duplicated in the entity plan")
    if reason == "orphan":
        raise BoardError("orphan return requires the claim row to be absent")
    row_match = row_matches[0]
    state = row_match.group(1)
    if reason == "handback":
        if state not in {"pending", "in_progress"}:
            raise BoardError("owner handback requires a pending or in-progress row")
        return
    if reason == "completed":
        if state != "completed" or not progress_proof_receipts(text, row):
            raise BoardError("completed return requires the completed row and its PROOF receipt")
        return
    if reason == "blocked":
        matching_wakes = []
        for line in section_lines(text, "Deferred"):
            match = re.match(r"^- (?P<id>~[0-9a-z]{4})(?:\s|$)", line)
            if (
                match is not None
                and match.group("id") == row
                and re.search(r"(?:^|\| )wake: \S", line)
            ):
                matching_wakes.append(line)
        if len(matching_wakes) != 1:
            raise BoardError("blocked return requires one Deferred entry naming the row and wake")
        if state != "blocked":
            raise BoardError("blocked return requires the project row to be blocked")
        return
    raise BoardError("claim return reason is not supported")


def section_lines(text: str, section: str) -> list[str]:
    """Return body lines from every canonical prefix-matched H2 section."""
    active = False
    result: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            active = name == section or name.startswith(section + " ")
            continue
        if active:
            result.append(line)
    return result


PROGRESS_PROOF_RECEIPT_RE = _grammar.PROOF_RECEIPT_RE


def progress_proof_receipt(line: str) -> tuple[str, str, str] | None:
    """Parse one canonical receipt line for lint and claim-return parity."""
    return _grammar.progress_proof_receipt(line)


def progress_proof_receipts(text: str, row: str) -> list[tuple[str, str]]:
    """Parse only the row's canonical Progress receipts, never notes elsewhere."""
    receipts: list[tuple[str, str]] = []
    for line in section_lines(text, "Progress"):
        receipt = progress_proof_receipt(line)
        if receipt is not None and receipt[0] == row:
            receipts.append((receipt[1], receipt[2]))
    return receipts


def has_accept_proof_receipt(text: str, row: str, argv: list[str]) -> bool:
    expected = (shlex.join(argv), "pass (accept)")
    return expected in progress_proof_receipts(text, row)


def _claim_huddles(payload: dict, claim: dict) -> list[dict]:
    ref = _claim_ref(claim) if payload["schema"] == V2_SCHEMA else None
    return [h for h in payload.get("huddles", []) if h["state"] != "resolved"
            and (ref in h["claims"] or h["resolution"] is not None
                 and ref in h["resolution"]["write_owners"])]


def _check_huddle_release(payload: dict, claim: dict, *, reason: str,
                          text: str = "", plan_root: str | None = None) -> None:
    """Refuse before side effects; the committing transaction repeats this gate."""
    if payload["schema"] != V2_SCHEMA:
        return
    ref = _claim_ref(claim)
    for h in _claim_huddles(payload, claim):
        if h["state"] == "remote_pending":
            raise BoardError("Huddle remote ownership requires stable readback before return or accept")
        if reason == "completed":
            if ref in h["holds"] or h["state"] == "awaiting_compliance":
                raise BoardError("Huddle held or pending-compliance claim cannot accept")
        elif h["state"] == "awaiting_compliance":
            entry = next((e for e in h["compliance"] if e["claim"] == ref and e["status"] == "pending"), None)
            if entry is None:
                raise BoardError("Huddle selected owner must wait for pending canonical returns")
            contradiction = any(_grammar.contradiction_is_open(line)
                and claim["row"] in _grammar.NEEDS_REF_RE.findall(line)
                for line in section_lines(text, "Contradictions"))
            if (plan_root is None or plan_root == entry["plan_root_at_settlement"]
                or not (reason == "blocked" or reason == "handback" and contradiction)):
                raise BoardError("Huddle required return needs a newer canonical blocker or contradiction")
    # A support bid binds this exact independent claim until the participant
    # returns. Closing it first would strand the live resolution's evidence.
    if any(b["support_claim"] == ref and b["round"] == h["round"]
           for h in payload.get("huddles", []) if h["state"] != "resolved" for b in h["bids"]):
        raise BoardError("Huddle support claim must remain current until its participant returns")


def check_huddle_release(plan: Path, claim: dict, *, reason: str,
                          home: Path | None = None) -> None:
    """Read-only preflight for accept workers and remote return side effects."""
    with _transaction(home) as (_, _, payload):
        current = next((c for c in payload["claims"]
                        if (c["entity"], c["row"]) == (claim["entity"], claim["row"])), None)
        if current is None or any(current.get(k) != v for k, v in claim.items() if k != "revision"):
            raise BoardError("claim changed before Huddle lifecycle preflight")
        text = read_plan_text(plan) if reason != "completed" else ""
        _check_huddle_release(payload, current, reason=reason, text=text,
                              plan_root=plan_state_token(plan) if text else None)


def _depart_huddles(
    payload: dict,
    claim: dict,
    *,
    now: datetime,
    completion_kind: str = "return",
    completion_receipt: str = "self",
) -> None:
    """Update membership and claim release in their one existing board commit."""
    if payload["schema"] != V2_SCHEMA:
        return
    ref = _claim_ref(claim)
    current = {_claim_key(c): c for c in payload["claims"]}
    for h in _claim_huddles(payload, claim):
        h["generation"] += 1
        if h["state"] == "awaiting_compliance":
            entry = next((e for e in h["compliance"]
                          if e["claim"] == ref and e["status"] == "pending"), None)
            if entry is not None:
                entry.update(status="satisfied", completion={
                    "kind": completion_kind,
                    "board_revision": payload["revision"] + 1,
                    "receipt": completion_receipt,
                })
            h["holds"] = [e["claim"] for e in h["compliance"] if e["status"] == "pending"]
            if not h["holds"]:
                h.update(state="resolved", resolved_at=_stamp(now),
                         retain_until=_stamp(now + timedelta(hours=24)))
            continue
        h["claims"] = [c for c in h["claims"] if c != ref]
        h["edges"] = [e for e in h["edges"] if ref not in (e["left"], e["right"])]
        h["bids"] = []
        h["holds"] = claim_holds(h)
        if len(h["claims"]) == 1 or not h["edges"]:
            single = len(h["claims"]) == 1
            h.update(state="resolved", reply_by=None, resolved_at=_stamp(now),
                     retain_until=_stamp(now + timedelta(hours=24)))
            h["resolution"] = dict(settled_revision=payload["revision"] + 1, settled_at=_stamp(now),
                rule="exact_claim_owner" if single else "path_disjoint", handoff=None,
                write_owners=[r for r in h["claims"] if current[_claim_key(r)]["access"] == "write"],
                actions=[dict(claim=r, action="continue" if single else "continue_disjoint") for r in h["claims"]],
                support_actions=[])
        else:
            unknown = any("scope_unknown" in e["kinds"] for e in h["edges"])
            h.update(state="awaiting_scope" if unknown else "open_round_1", round=0 if unknown else 1,
                     reply_by=_stamp(now + timedelta(minutes=2)))


def _require_expected_claim(payload: dict, claim: dict | None, expected_claim: dict | None) -> None:
    if expected_claim is None:
        return
    fields = ("entity", "row", "owner", "claimed_at", "return_by", "recovery")
    if payload["schema"] == V2_SCHEMA:
        fields += ("claim_revision", "access", "repository_binding", "write_scope")
    if (not isinstance(expected_claim, dict) or claim is None
        or any(claim.get(key) != expected_claim.get(key) for key in fields)):
        raise BoardError("claim changed before completion could close it; reconcile the proven row")


def _reserve_claim_receipt(
    plan: Path,
    row: str,
    owner: str,
    *,
    expected_plan: dict[str, str] | None = None,
    expected_claim: dict | None = None,
    protect_until: datetime | None = None,
    home: Path | None = None,
) -> dict:
    """Return one exact owned claim, optionally extending its bounded lease."""
    if not regular_plan(plan):
        raise BoardError("claim completion requires a regular, non-symlink PLAN.md")
    if ROW_ID.fullmatch(row) is None:
        raise BoardError("claim completion target must carry one row id")
    owner = validate_owner(owner)
    plan = plan.resolve()
    with _transaction(home) as (root, path, payload):
        if expected_plan is not None:
            observed, _ = frozen_plan_snapshot(plan, home=home)
            if observed != expected_plan:
                raise BoardError("entity plan changed while its proof ran; retry")
        entity = _entity_for(payload, plan)
        if entity is None:
            raise BoardError("entity is not registered on this computer")
        claim = next(
            (
                item for item in payload["claims"]
                if (item["entity"], item["row"]) == (entity["id"], row)
            ),
            None,
        )
        if claim is None:
            raise BoardError(f"{row} is not claimed; run shadow throw first")
        _require_expected_claim(payload, claim, expected_claim)
        if claim["owner"] != owner:
            raise BoardError(f"claim is owned by {claim['owner']}")
        _check_huddle_release(payload, claim, reason="completed")
        if protect_until is not None:
            protected = protect_until.astimezone(timezone.utc)
            if _timestamp(claim["return_by"], "claim return-by") < protected:
                claim["return_by"] = _stamp(protected)
                payload["revision"] += 1
                _validate(payload)
                _write_and_commit(
                    root, path, payload, f"shadow board: reserve completion {row}"
                )
        receipt = json.loads(json.dumps(claim))
        receipt["revision"] = payload["revision"]
        return receipt


def reserve_completion(
    plan: Path,
    row: str,
    owner: str,
    *,
    expected_plan: dict[str, str],
    expected_claim: dict | None = None,
    now: datetime | None = None,
    home: Path | None = None,
) -> dict:
    """Keep the current owner live for one bounded project-commit window."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return _reserve_claim_receipt(
        plan,
        row,
        owner,
        expected_plan=expected_plan,
        expected_claim=expected_claim,
        protect_until=current + timedelta(minutes=COMPLETION_RESERVATION_MINUTES),
        home=home,
    )


def release(
    plan: Path,
    row: str,
    *,
    resumes: list[str] | None = None,
    owner: str | None = None,
    reason: str = "completed",
    expected_plan: dict[str, str] | None = None,
    expected_text: str | None = None,
    expected_claim: dict | None = None,
    now: datetime | None = None,
    home: Path | None = None,
) -> tuple[dict, bool] | None:
    if not regular_plan(plan):
        raise BoardError("claim return requires a regular, non-symlink PLAN.md")
    plan = plan.resolve()
    if owner is not None:
        owner = validate_owner(owner)
    if snapshot(home=home) is None:
        return None
    with _transaction(home) as (root, path, payload):
        if expected_plan is not None:
            observed, observed_bytes = frozen_plan_snapshot(plan, home=home)
            try:
                observed_text = observed_bytes.decode("utf-8")
            except UnicodeError as exc:
                raise BoardError("claim return needs a UTF-8 entity plan") from exc
            if observed != expected_plan or observed_text != expected_text:
                raise BoardError("entity plan changed before the claim return committed; retry")
        entity = _entity_for(payload, plan, exact_on_conflict=True)
        if entity is None:
            return None
        identity = entity["id"]
        claim = next(
            (
                item for item in payload["claims"]
                if (item["entity"], item["row"]) == (identity, row)
            ),
            None,
        )
        _require_expected_claim(payload, claim, expected_claim)
        if claim is not None and owner != claim["owner"]:
            raise BoardError(f"claim is owned by {claim['owner']}")
        content = read_plan_text(plan) if claim is not None else ""
        plan_root = plan_state_token(plan) if claim is not None else None
        if claim is not None:
            _release_state(plan, row, reason, text=expected_text if expected_text is not None else content)
            _check_huddle_release(payload, claim, reason=reason, text=content, plan_root=plan_root)
        kept = [item for item in payload["claims"] if item is not claim]
        had_claim = len(kept) != len(payload["claims"])
        if claim is None:
            # A repeated owner return after the atomic close is a no-op. There
            # is no live claim to steal and no half-written resume state to
            # repair because both changed in the same board transaction.
            return json.loads(json.dumps(payload)), False
        if entity["plan"] != str(plan) and not regular_plan(Path(entity["plan"])):
            entity["plan"] = str(plan)
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        _depart_huddles(payload, claim, now=current)
        payload["claims"] = kept
        candidates = resumes or []
        if any(ROW_ID.fullmatch(candidate) is None for candidate in candidates):
            raise BoardError("next resume candidates must be row ids")
        claimed = {
            item["row"] for item in kept if item["entity"] == identity
        }
        resume = _choose_resume(entity["resume"], candidates, claimed)
        changed = had_claim or entity["resume"] != resume
        entity["resume"] = resume
        if not changed:
            return json.loads(json.dumps(payload)), False
        payload["revision"] += 1
        _validate(payload)
        def guard():
            if read_plan_text(plan) != content or plan_state_token(plan) != plan_root:
                raise BoardError("canonical plan changed before claim return committed")
        _write_and_commit(root, path, payload, f"shadow board: release {row}", guard=guard, now=current)
        return json.loads(json.dumps(payload)), True


def release_stranded_completed_claims(
    *,
    now: datetime | None = None,
    home: Path | None = None,
) -> int:
    """Drop stale claims whose plan row already completed with its PROOF receipt.

    The plan is the authority for row state; refresh only stops contradicting
    it. A claim qualifies only when its lease is overdue: a live lease can be
    the owner's own accept still publishing its close, and refresh must never
    race that. Rows still pending or in progress keep their claims — expiry
    marks those stale and explicit adoption handles them; refresh never
    fabricates a close for unfinished work. The predicate reads the same
    authority release would: committed state for a Git-backed plan (a dirty
    worktree skips the claim, never authorizes the drop), the working file
    for a machine-local one.
    """
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payload = snapshot(home=home)
    if payload is None:
        return 0
    plans = {
        entity["id"]: entity["plan"]
        for entity in payload["entities"]
        if isinstance(entity.get("plan"), str)
    }
    stranded = [
        (claim["entity"], claim["row"], _claim_ref(claim) if payload["schema"] == V2_SCHEMA else None)
        for claim in payload["claims"]
        if claim_is_stale(claim, now=current) and plans.get(claim["entity"]) is not None
    ]
    released = 0
    for identity, row, expected_ref in stranded:
        locator = plans[identity]
        if not regular_plan(Path(locator)):
            continue
        plan = Path(locator).resolve()
        with _transaction(home) as (root, path, fresh):
            claim = next(
                (
                    item for item in fresh["claims"]
                    if (item["entity"], item["row"]) == (identity, row)
                ),
                None,
            )
            if (claim is None or not claim_is_stale(claim, now=current)
                    or expected_ref is not None and _claim_ref(claim) != expected_ref):
                continue
            try:
                plan_token, frozen = frozen_plan_snapshot(plan, home=home)
                plan_state = plan_state_token(plan)
                try:
                    text = frozen.decode("utf-8")
                except UnicodeError:
                    continue
                _release_state(plan, row, "completed", text=text)
            except BoardError:
                continue
            # A remote handoff has no authoritative local successor yet.  Its
            # stale lease cannot settle until exact remote ownership readback.
            if any(h["state"] == "remote_pending" for h in _claim_huddles(fresh, claim)):
                continue
            receipt_lines = [
                line for line in section_lines(text, "Progress")
                if (receipt := progress_proof_receipt(line)) is not None and receipt[0] == row
            ]
            receipt_digest = hashlib.sha256("\n".join(receipt_lines).encode("utf-8")).hexdigest()
            _depart_huddles(
                fresh,
                claim,
                now=current,
                completion_kind="proof_first_stale_recovery",
                completion_receipt=receipt_digest,
            )
            fresh["claims"] = [item for item in fresh["claims"] if item is not claim]
            fresh["revision"] += 1
            _validate(fresh)
            def guard():
                observed_token, observed = frozen_plan_snapshot(plan, home=home)
                if (observed_token != plan_token or observed != frozen
                        or plan_state_token(plan) != plan_state):
                    raise BoardError("canonical plan changed before stale completion committed")
            _write_and_commit(root, path, fresh, f"shadow board: release {row}", guard=guard, now=current)
            released += 1
    return released


def set_priority(plan: Path, priority: int, *, home: Path | None = None) -> dict:
    """Change global project priority through the board transaction."""
    if isinstance(priority, bool) or priority not in range(1, 6):
        raise BoardError("project priority must be 1-5")
    with _transaction(home) as (root, path, payload):
        entity = _entity_for(payload, plan)
        if entity is None:
            raise BoardError("entity is not registered on this computer")
        project = next(
            item for item in payload["projects"] if item["id"] == entity["project"]
        )
        if project["priority"] == priority:
            return json.loads(json.dumps(payload))
        project["priority"] = priority
        payload["projects"].sort(key=lambda item: (item["priority"], item["id"]))
        payload["revision"] += 1
        _validate(payload)
        _write_and_commit(
            root, path, payload, f"shadow board: set project priority {priority}"
        )
        return json.loads(json.dumps(payload))


def _migration_plan_rows(expected: object) -> set[str]:
    if not isinstance(expected, dict) or set(expected) != {
        "relative",
        "entity_id",
        "head",
        "blob",
        "logical_sha256",
        "rows",
        "candidates",
    }:
        raise BoardError("project-map migration plan receipt is malformed")
    relative = expected["relative"]
    relative_path = Path(relative) if isinstance(relative, str) else Path()
    if (
        not isinstance(relative, str)
        or relative_path.is_absolute()
        or relative_path.name != "PLAN.md"
        or any(part in {"", ".", ".."} for part in relative_path.parts)
        or not isinstance(expected["entity_id"], str)
        or ENTITY_ID.fullmatch(expected["entity_id"]) is None
        or not isinstance(expected["head"], str)
        or not expected["head"]
        or not isinstance(expected["blob"], str)
        or not expected["blob"]
        or not isinstance(expected["logical_sha256"], str)
        or ENTITY_ID.fullmatch(expected["logical_sha256"]) is None
    ):
        raise BoardError("project-map migration plan receipt is malformed")
    rows = expected["rows"]
    candidates = expected["candidates"]
    if (
        not isinstance(rows, list)
        or not isinstance(candidates, list)
        or any(not isinstance(row, str) or ROW_ID.fullmatch(row) is None for row in rows)
        or any(
            not isinstance(row, str) or ROW_ID.fullmatch(row) is None
            for row in candidates
        )
        or len(rows) != len(set(rows))
        or len(candidates) != len(set(candidates))
        or not set(candidates).issubset(rows)
    ):
        raise BoardError("project-map migration rows are malformed")
    return set(rows)


def _migration_destinations(
    plans: dict[str, object],
    row_map: object,
) -> dict[str, str]:
    source_rows = _migration_plan_rows(plans["source"])
    root_rows = _migration_plan_rows(plans["root"])
    child_rows = _migration_plan_rows(plans["child"])
    if root_rows.intersection(child_rows) or root_rows.union(child_rows) != source_rows:
        raise BoardError(
            "project-map migration plans do not partition the source rows"
        )
    derived = {
        row: "root" if row in root_rows else "child"
        for row in source_rows
    }
    if not isinstance(row_map, list):
        raise BoardError("project-map migration row map is malformed")
    declared: dict[str, str] = {}
    for item in row_map:
        if (
            not isinstance(item, dict)
            or set(item) != {"row", "destination"}
            or not isinstance(item["row"], str)
            or ROW_ID.fullmatch(item["row"]) is None
            or item["destination"] not in {"root", "child"}
            or item["row"] in declared
        ):
            raise BoardError("project-map migration row map is malformed")
        declared[item["row"]] = item["destination"]
    if declared != derived:
        raise BoardError(
            "project-map migration row map does not match actual plan membership"
        )
    return derived


def _migration_plan_matches(plan: Path, expected: dict[str, object]) -> bytes:
    _migration_plan_rows(expected)
    token, content = committed_plan_snapshot(plan)
    logical_sha256 = hashlib.sha256(content).hexdigest()
    if (
        token["relative"] != expected["relative"]
        or token["head"] != expected["head"]
        or token["blob"] != expected["blob"]
        or entity_id(plan) != expected["entity_id"]
        or logical_sha256 != expected["logical_sha256"]
    ):
        raise BoardError("project-map migration plan changed; rerun the dry run")
    observed_rows = {
        match.group("id")
        for line in content.decode("utf-8").splitlines()
        if (match := _grammar.ROW_RE.fullmatch(line)) is not None
    }
    if observed_rows != set(expected["rows"]):
        raise BoardError("project-map migration plan rows changed")
    if _grammar.candidate_row_ids(content.decode("utf-8")) != expected["candidates"]:
        raise BoardError("project-map migration resume candidates changed")
    return content


def _safe_migration_claims(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise BoardError("project-map migration claims are malformed")
    claims = json.loads(json.dumps(value))
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {
            "entity",
            "row",
            "owner",
            "claimed_at",
            "return_by",
            "recovery",
        }:
            raise BoardError("project-map migration claims are malformed")
    return claims


def apply_project_map_migration(
    root_plan: Path,
    child_plan: Path,
    prepared: dict[str, object],
    *,
    home: Path | None = None,
) -> dict:
    """Atomically add one child entity and rekey explicitly mapped claims."""
    root_plan = root_plan.resolve()
    child_plan = child_plan.resolve()
    if prepared.get("schema") != "shadow.project-map-migration.v1":
        raise BoardError("project-map migration receipt schema is not supported")
    board_receipt = prepared.get("board")
    plans = prepared.get("plans")
    row_map = prepared.get("row_map")
    if (
        not isinstance(board_receipt, dict)
        or not isinstance(plans, dict)
        or set(plans) != {"source", "root", "child"}
    ):
        raise BoardError("project-map migration receipt is malformed")
    before = board_receipt.get("before")
    if not isinstance(before, dict) or set(before) != {
        "revision",
        "raw_sha256",
        "authority_sha256",
        "project",
        "root_entity",
        "claims",
        "journal_head",
    }:
        raise BoardError("project-map migration board receipt is malformed")
    expected_project = before["project"]
    expected_root = before["root_entity"]
    if (
        not isinstance(expected_project, dict)
        or set(expected_project) != {"id", "priority"}
        or not isinstance(expected_root, dict)
        or set(expected_root) != {"id", "project", "resume"}
        or not isinstance(before["journal_head"], str)
    ):
        raise BoardError("project-map migration authority receipt is malformed")
    expected_claims = _safe_migration_claims(before["claims"])
    destinations = _migration_destinations(plans, row_map)
    _migration_plan_matches(root_plan, plans["root"])
    _migration_plan_matches(child_plan, plans["child"])
    with _transaction(home) as (root, path, payload):
        try:
            raw_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise BoardError("root board could not be frozen") from exc
        if (
            payload["revision"] != before["revision"]
            or raw_sha256 != before["raw_sha256"]
            or board_authority_sha256(payload) != before["authority_sha256"]
            or _journal_head(root) != before["journal_head"]
        ):
            raise BoardError("root board changed during project-map migration")
        _migration_plan_matches(root_plan, plans["root"])
        _migration_plan_matches(child_plan, plans["child"])
        root_entity = next(
            (item for item in payload["entities"] if item["id"] == expected_root["id"]),
            None,
        )
        if root_entity is None or {
            "id": root_entity["id"],
            "project": root_entity["project"],
            "resume": root_entity["resume"],
        } != expected_root or root_entity["plan"] != str(root_plan):
            raise BoardError("root entity changed during project-map migration")
        project = next(
            (item for item in payload["projects"] if item["id"] == expected_project["id"]),
            None,
        )
        if project != expected_project:
            raise BoardError("project priority changed during project-map migration")
        current_claims = sorted(
            (
                json.loads(json.dumps(item))
                for item in payload["claims"]
                if item["entity"] == root_entity["id"]
            ),
            key=lambda item: (item["entity"], item["row"]),
        )
        if current_claims != sorted(
            expected_claims,
            key=lambda item: (item["entity"], item["row"]),
        ):
            raise BoardError("claims changed during project-map migration")
        missing_mapping = next(
            (claim["row"] for claim in current_claims if claim["row"] not in destinations),
            None,
        )
        if missing_mapping is not None:
            raise BoardError(
                f"project-map migration claim {missing_mapping} has no destination"
            )
        child_id = plans["child"]["entity_id"]
        if any(item["id"] == child_id for item in payload["entities"]):
            raise BoardError("project-map migration child is already registered")
        for claim in payload["claims"]:
            if (
                claim["entity"] == root_entity["id"]
                and destinations.get(claim["row"]) == "child"
            ):
                claim["entity"] = child_id
        root_claimed = {
            claim["row"]
            for claim in payload["claims"]
            if claim["entity"] == root_entity["id"]
        }
        child_claimed = {
            claim["row"]
            for claim in payload["claims"]
            if claim["entity"] == child_id
        }
        previous_resume = root_entity["resume"]
        root_entity["resume"] = _choose_resume(
            previous_resume if destinations.get(previous_resume) == "root" else None,
            plans["root"]["candidates"],
            root_claimed,
        )
        child_entity = {
            "id": child_id,
            "project": root_entity["project"],
            "plan": str(child_plan),
            "resume": _choose_resume(
                previous_resume if destinations.get(previous_resume) == "child" else None,
                plans["child"]["candidates"],
                child_claimed,
            ),
        }
        payload["entities"].append(child_entity)
        payload["projects"].sort(key=lambda item: (item["priority"], item["id"]))
        payload["entities"].sort(key=lambda item: (item["project"], item["id"]))
        payload["claims"].sort(key=lambda item: (item["entity"], item["row"]))
        payload["revision"] += 1
        _validate(payload)
        _write_and_commit(
            root,
            path,
            payload,
            "shadow board: apply project-map migration",
        )
        return json.loads(json.dumps(payload))


def _project_map_rollback_payload(
    payload: dict,
    root_plan: Path,
    child_plan: Path,
    before: dict[str, object],
    plans: dict[str, object],
    destinations: dict[str, str],
) -> dict:
    expected_root = before["root_entity"]
    expected_project = before["project"]
    expected_claims = _safe_migration_claims(before["claims"])
    root_id = expected_root["id"]
    child_id = plans["child"]["entity_id"]
    if (
        expected_root["project"] != expected_project["id"]
        or plans["source"]["entity_id"] != root_id
        or plans["root"]["entity_id"] != root_id
        or child_id == root_id
        or payload["revision"] != before["revision"] + 1
    ):
        raise BoardError("project-map applied authority does not match its receipt")
    project = next(
        (item for item in payload["projects"] if item["id"] == expected_project["id"]),
        None,
    )
    root_entity = next(
        (item for item in payload["entities"] if item["id"] == root_id),
        None,
    )
    child_entity = next(
        (item for item in payload["entities"] if item["id"] == child_id),
        None,
    )
    expected_applied_claims = json.loads(json.dumps(expected_claims))
    for claim in expected_applied_claims:
        if destinations.get(claim["row"]) == "child":
            claim["entity"] = child_id
    expected_applied_claims.sort(key=lambda item: (item["entity"], item["row"]))
    actual_applied_claims = sorted(
        (
            json.loads(json.dumps(item))
            for item in payload["claims"]
            if item["entity"] in {root_id, child_id}
        ),
        key=lambda item: (item["entity"], item["row"]),
    )
    root_claimed = {
        claim["row"]
        for claim in expected_applied_claims
        if claim["entity"] == root_id
    }
    child_claimed = {
        claim["row"]
        for claim in expected_applied_claims
        if claim["entity"] == child_id
    }
    previous_resume = expected_root["resume"]
    expected_root_resume = _choose_resume(
        previous_resume if destinations.get(previous_resume) == "root" else None,
        plans["root"]["candidates"],
        root_claimed,
    )
    expected_child_resume = _choose_resume(
        previous_resume if destinations.get(previous_resume) == "child" else None,
        plans["child"]["candidates"],
        child_claimed,
    )
    if (
        project != expected_project
        or root_entity
        != {
            "id": root_id,
            "project": expected_root["project"],
            "plan": str(root_plan),
            "resume": expected_root_resume,
        }
        or child_entity
        != {
            "id": child_id,
            "project": expected_root["project"],
            "plan": str(child_plan),
            "resume": expected_child_resume,
        }
        or actual_applied_claims != expected_applied_claims
    ):
        raise BoardError("project-map state changed after apply")
    restored = json.loads(json.dumps(payload))
    for claim in restored["claims"]:
        if claim["entity"] == child_id:
            claim["entity"] = root_id
    restored_root = next(
        item for item in restored["entities"] if item["id"] == root_id
    )
    restored_root["project"] = expected_root["project"]
    restored_root["plan"] = str(root_plan)
    restored_root["resume"] = expected_root["resume"]
    restored["entities"] = [
        item for item in restored["entities"] if item["id"] != child_id
    ]
    restored["projects"].sort(key=lambda item: (item["priority"], item["id"]))
    restored["entities"].sort(key=lambda item: (item["project"], item["id"]))
    restored["claims"].sort(key=lambda item: (item["entity"], item["row"]))
    _validate(restored)
    if board_authority_sha256(restored) != before["authority_sha256"]:
        raise BoardError("project-map rollback would not restore exact authority")
    restored["revision"] += 1
    _validate(restored)
    return restored


def validate_project_map_migration_applied(
    root_plan: Path,
    child_plan: Path,
    receipt: dict[str, object],
    *,
    home: Path | None = None,
) -> dict:
    """Read-only proof that one immutable receipt names the exact applied state."""
    root_plan = root_plan.resolve()
    child_plan = child_plan.resolve()
    if receipt.get("schema") != "shadow.project-map-migration.v1":
        raise BoardError("project-map migration receipt schema is not supported")
    board_receipt = receipt.get("board")
    plans = receipt.get("plans")
    row_map = receipt.get("row_map")
    if (
        not isinstance(board_receipt, dict)
        or set(board_receipt) != {"before"}
        or not isinstance(plans, dict)
        or set(plans) != {"source", "root", "child"}
    ):
        raise BoardError("project-map migration receipt is malformed")
    before = board_receipt["before"]
    if (
        not isinstance(before, dict)
        or set(before) != {
            "revision",
            "raw_sha256",
            "authority_sha256",
            "project",
            "root_entity",
            "claims",
            "journal_head",
        }
        or not isinstance(before["journal_head"], str)
    ):
        raise BoardError("project-map migration board receipt is malformed")
    destinations = _migration_destinations(plans, row_map)
    _migration_plan_matches(root_plan, plans["root"])
    _migration_plan_matches(child_plan, plans["child"])
    root = _safe_root(home)
    path = root / BOARD_NAME
    payload = snapshot(home=home)
    if payload is None:
        raise BoardError("root board is missing")
    clean = _git(root, "diff", "--quiet", "HEAD", "--", BOARD_NAME)
    if clean.returncode or _journal_parent(root) != before["journal_head"]:
        raise BoardError("project-map state changed after apply")
    _project_map_rollback_payload(
        payload,
        root_plan,
        child_plan,
        before,
        plans,
        destinations,
    )
    try:
        if path.read_bytes() != _encoded_board(payload):
            raise BoardError("project-map board bytes are not canonical")
    except OSError as exc:
        raise BoardError("root board could not be frozen") from exc
    return json.loads(json.dumps(payload))


def rollback_project_map_migration(
    root_plan: Path,
    child_plan: Path,
    applied: dict[str, object],
    *,
    home: Path | None = None,
) -> dict:
    """Atomically restore one monolith and every child-owned board claim."""
    root_plan = root_plan.resolve()
    child_plan = child_plan.resolve()
    if applied.get("schema") != "shadow.project-map-migration.v1":
        raise BoardError("project-map migration receipt schema is not supported")
    board_receipt = applied.get("board")
    plans = applied.get("plans")
    row_map = applied.get("row_map")
    if (
        not isinstance(board_receipt, dict)
        or set(board_receipt) != {"before"}
        or not isinstance(plans, dict)
        or set(plans) != {"source", "root", "child"}
    ):
        raise BoardError("project-map rollback receipt is malformed")
    before = board_receipt.get("before")
    if (
        not isinstance(before, dict)
        or set(before) != {
            "revision",
            "raw_sha256",
            "authority_sha256",
            "project",
            "root_entity",
            "claims",
            "journal_head",
        }
        or not isinstance(before["journal_head"], str)
    ):
        raise BoardError("project-map rollback board receipt is malformed")
    destinations = _migration_destinations(plans, row_map)
    _migration_plan_matches(root_plan, plans["source"])
    if child_plan.exists() or child_plan.is_symlink():
        raise BoardError("project-map rollback requires the source tree")
    with _transaction(home) as (root, path, payload):
        if _journal_parent(root) != before["journal_head"]:
            raise BoardError("root board changed after project-map migration")
        restored = _project_map_rollback_payload(
            payload,
            root_plan,
            child_plan,
            before,
            plans,
            destinations,
        )
        _write_and_commit(
            root,
            path,
            restored,
            "shadow board: roll back project-map migration",
        )
        return json.loads(json.dumps(restored))


def validate_project_map_migration_rolled_back(
    root_plan: Path,
    child_plan: Path,
    receipt: dict[str, object],
    *,
    home: Path | None = None,
) -> dict:
    """Read-only proof that retrying rollback observes its exact final state."""
    root_plan = root_plan.resolve()
    child_plan = child_plan.resolve()
    if receipt.get("schema") != "shadow.project-map-migration.v1":
        raise BoardError("project-map migration receipt schema is not supported")
    board_receipt = receipt.get("board")
    plans = receipt.get("plans")
    row_map = receipt.get("row_map")
    if (
        not isinstance(board_receipt, dict)
        or set(board_receipt) != {"before"}
        or not isinstance(plans, dict)
        or set(plans) != {"source", "root", "child"}
    ):
        raise BoardError("project-map migration receipt is malformed")
    before = board_receipt["before"]
    if (
        not isinstance(before, dict)
        or set(before) != {
            "revision",
            "raw_sha256",
            "authority_sha256",
            "project",
            "root_entity",
            "claims",
            "journal_head",
        }
        or not isinstance(before["journal_head"], str)
    ):
        raise BoardError("project-map migration board receipt is malformed")
    _migration_destinations(plans, row_map)
    _migration_plan_matches(root_plan, plans["source"])
    if child_plan.exists() or child_plan.is_symlink():
        raise BoardError("project-map rollback did not remove the child plan")
    root = _safe_root(home)
    path = root / BOARD_NAME
    payload = snapshot(home=home)
    if payload is None:
        raise BoardError("root board is missing")
    rollback_parent = _journal_parent(root)
    if (
        rollback_parent is None
        or _commit_parent(root, rollback_parent) != before["journal_head"]
        or payload["revision"] != before["revision"] + 2
        or board_authority_sha256(payload) != before["authority_sha256"]
        or _git(root, "diff", "--quiet", "HEAD", "--", BOARD_NAME).returncode
    ):
        raise BoardError("project-map rollback final state is invalid")
    try:
        if path.read_bytes() != _encoded_board(payload):
            raise BoardError("project-map board bytes are not canonical")
    except OSError as exc:
        raise BoardError("root board could not be frozen") from exc
    return json.loads(json.dumps(payload))


def migrate_to_local_plan(source: Path, destination: Path, *, home: Path | None = None) -> dict:
    """Move one registered authority to a byte-identical local plan atomically.

    This is intentionally a migration primitive, not another plan registry. It
    preserves a live claim while removing a source checkout from the board.
    """
    source = source.resolve()
    destination = destination.resolve()
    if not regular_plan(source) or not regular_plan(destination):
        raise BoardError("plan migration requires regular non-symlink PLAN.md files")
    if not is_local_plan(destination, home=home):
        raise BoardError("plan migration destination must live below ~/.shadow/plans")
    source_bytes = read_plan_bytes(source)
    if source_bytes != read_plan_bytes(destination):
        raise BoardError("plan migration requires byte-identical source and local copies")
    board = snapshot(home=home)
    for claim in board.get("claims", []) if board else []:
        if claim.get("entity") == entity_id(source) and claim.get("row", "") not in source_bytes.decode("utf-8", errors="ignore"):
            raise BoardError("plan migration source no longer carries a live claim row")
    old_id = entity_id(source)
    new_id = entity_id(destination)
    with _transaction(home) as (root, path, payload):
        entity = next((item for item in payload["entities"] if item["id"] == old_id), None)
        if entity is None:
            raise BoardError("source plan is not registered on this computer")
        if any(item["id"] == new_id for item in payload["entities"] if item is not entity):
            raise BoardError("local plan already has a registered authority")
        if read_plan_bytes(source) != source_bytes or read_plan_bytes(destination) != source_bytes:
            raise BoardError("plan changed during local migration; retry")
        entity["id"] = new_id
        entity["plan"] = str(destination)
        for claim in payload["claims"]:
            if claim["entity"] == old_id:
                claim["entity"] = new_id
        payload["entities"].sort(key=lambda item: (item["project"], item["id"]))
        payload["claims"].sort(key=lambda item: (item["entity"], item["row"]))
        payload["revision"] += 1
        _validate(payload)
        _write_and_commit(root, path, payload, "shadow board: move authority to local plan")
        return json.loads(json.dumps(payload))


def discard_unclaimed_source_alias(
    source: Path,
    destination: Path,
    *,
    home: Path | None = None,
) -> dict:
    """Drop a stale source alias when its private authority already exists.

    This cannot choose between two resume rows or make a source checkout
    authoritative. It only repairs duplicate aliases produced by an older
    importer after the local plan is already registered. A live claim follows
    only when its exact row exists exclusively in that private plan.
    """
    source = source.resolve()
    destination = destination.resolve()
    # The source side is deliberately allowed to be absent.  Once an
    # operational plan has been moved under ``~/.shadow/plans``, a later
    # source cleanup can remove the old file before an older board entry is
    # refreshed.  The registered source locator is then only stale metadata;
    # the private plan and its rows remain the authority.  A present source
    # must still be a regular file, so a symlink cannot smuggle a different
    # authority into this cleanup path.
    if source.exists() and not regular_plan(source):
        raise BoardError("alias cleanup source is not a regular non-symlink PLAN.md file")
    if not regular_plan(destination):
        raise BoardError("alias cleanup requires a regular non-symlink private PLAN.md")
    if not is_local_plan(destination, home=home):
        raise BoardError("alias cleanup destination must live below ~/.shadow/plans")
    destination_id = entity_id(destination)
    destination_rows = set(
        _grammar.HASH_RE.findall(read_plan_bytes(destination).decode("utf-8"))
    )
    with _transaction(home) as (root, path, payload):
        source_entity = next(
            (item for item in payload["entities"] if item["plan"] == str(source)),
            None,
        )
        destination_entity = next(
            (item for item in payload["entities"] if item["plan"] == str(destination)),
            None,
        )
        if source_entity is None:
            return json.loads(json.dumps(payload))
        if destination_entity is None:
            raise BoardError("alias cleanup requires the private authority to be registered")
        source_id = source_entity["id"]
        old_destination_id = destination_entity["id"]
        if source_id == old_destination_id:
            raise BoardError("alias cleanup requires distinct source and local entities")
        source_claims = [item for item in payload["claims"] if item["entity"] == source_id]
        missing_claim = next(
            (item["row"] for item in source_claims if item["row"] not in destination_rows),
            None,
        )
        if missing_claim is not None:
            raise BoardError("alias cleanup source claim is absent from the private plan")
        destination_claims = {
            item["row"] for item in payload["claims"] if item["entity"] == old_destination_id
        }
        duplicated_claim = next(
            (item["row"] for item in source_claims if item["row"] in destination_claims),
            None,
        )
        if duplicated_claim is not None:
            raise BoardError("alias cleanup refuses duplicate source and local claims")
        source_resume = source_entity["resume"]
        if source_resume is not None and source_resume not in destination_rows:
            raise BoardError("alias cleanup source resume is absent from the private plan")
        if (
            source_resume is not None
            and destination_entity["resume"] is not None
            and destination_entity["resume"] != source_resume
        ):
            raise BoardError("alias cleanup refuses divergent source and local resumes")
        if destination_entity["resume"] is None and source_resume is not None:
            destination_entity["resume"] = source_resume
        if (
            old_destination_id != destination_id
            and any(
                item["id"] == destination_id
                for item in payload["entities"]
                if item is not destination_entity
            )
        ):
            raise BoardError("alias cleanup local identity collides with another entity")
        destination_entity["id"] = destination_id
        for claim in payload["claims"]:
            if claim["entity"] == old_destination_id:
                claim["entity"] = destination_id
            elif claim["entity"] == source_id:
                claim["entity"] = destination_id
        payload["entities"] = [
            item for item in payload["entities"] if item["id"] != source_id
        ]
        used_projects = {item["project"] for item in payload["entities"]}
        payload["projects"] = [
            item for item in payload["projects"] if item["id"] in used_projects
        ]
        payload["projects"].sort(key=lambda item: (item["priority"], item["id"]))
        payload["entities"].sort(key=lambda item: (item["project"], item["id"]))
        payload["claims"].sort(key=lambda item: (item["entity"], item["row"]))
        payload["revision"] += 1
        _validate(payload)
        _write_and_commit(root, path, payload, "shadow board: remove stale source alias")
        return json.loads(json.dumps(payload))


def _same_path(registered: str, candidate: Path) -> bool:
    """Whether a registered locator names the same file as ``candidate``."""
    try:
        return Path(registered).resolve() == candidate.resolve()
    except OSError:
        return False


def declared_local_alias_slug(entity: dict, local_only: dict[str, str]) -> str | None:
    """Return the private slug a missing locator is *proved* to alias.

    Identity of a deleted path cannot be re-read from disk, but the board
    already stores the hash that path's identity minted, and that hash
    reproduces only for the exact ``(repository origin, repository-relative
    path)`` pair it came from. Replaying the declared local-only origins
    against the locator's own path suffixes therefore either reproduces the
    stored id, which names both the missing locator's logical identity and the
    one private plan that is allowed to stand in for it, or proves nothing and
    returns ``None``.

    Project membership and resume rows deliberately do not participate: a
    project groups distinct entities on purpose and row ids are plan-local, so
    neither can establish that two entities are the same authority.
    """
    stored = entity["id"]
    parts = Path(entity["plan"]).parts
    relatives = ["/".join(parts[index:]) for index in range(1, len(parts))]
    for origin, slug in local_only.items():
        for relative in relatives:
            if logical_entity_id(origin, relative) == stored:
                return slug
    return None


def discard_missing_unclaimed_aliases(
    *,
    local_only: dict[str, str],
    home: Path | None = None,
) -> int:
    """Remove only a provably stale source locator from the private board.

    A migration can leave an old source ``PLAN.md`` locator after the plan has
    moved under the board's private ``plans/`` root, and a later cleanup can
    delete the source checkout entirely. Once the file is gone, the repair
    paths that resolve a locator's Git identity from disk cannot name it at
    all, so the phantom entity outlives every reconcile. This repair is
    deliberately narrower than identity reconciliation: it never reads,
    rekeys, claims, or releases the surviving entity, and it takes identity
    only from the board's own records rather than from the absent path.

    An alias is discarded only when its source file is absent, it owns no
    claim, and its stored id proves, through ``local_only``, that the locator
    belongs to a repository whose authority may only live at one private
    ``plans/<slug>/PLAN.md`` -- and that exact private plan is registered,
    carries the same project, and still holds the alias's resume row. Without
    that proof the entity is left alone: a shared project and a plan-local row
    id never make two entities the same authority, so a checkout that is
    merely absent for now keeps its last-known resume state. Existing or
    divergent source plans are never candidates either: they need an explicit
    migration decision rather than a status-time guess.
    """
    # Discovery calls this opportunistically before it has decided that this
    # computer needs a board. Do not turn a read-only first import into a
    # durable board directory merely to discover that there is nothing to
    # repair.
    if snapshot(home=home) is None:
        return 0
    with _transaction(home) as (root, path, payload):
        resolved_private_root = (root / "plans").resolve()
        repairs: list[dict] = []
        for source in payload["entities"]:
            source_path = Path(source["plan"])
            if source_path.exists() or source_path.is_symlink():
                continue
            resume = source["resume"]
            if resume is None:
                continue
            if any(claim["entity"] == source["id"] for claim in payload["claims"]):
                continue
            slug = declared_local_alias_slug(source, local_only)
            if slug is None:
                continue
            destination_path = resolved_private_root / slug / "PLAN.md"
            if not regular_plan(destination_path):
                continue
            destination = next(
                (
                    item
                    for item in payload["entities"]
                    if item is not source and _same_path(item["plan"], destination_path)
                ),
                None,
            )
            if destination is None or destination["project"] != source["project"]:
                continue
            # Reachability, never agreement. The surviving authority keeps
            # working, so its resume row moves on while a dead alias keeps
            # whatever row it pointed at the day its checkout vanished.
            # Requiring the two to still match made this repair fire only
            # inside the window where nothing had progressed, and left every
            # later phantom registered forever — measured 2026-08-16, a ghost
            # entity duplicated a project name for days and refused every
            # lifecycle successor. What must hold is that discarding the alias
            # loses no reachable state: its own resume row still exists in the
            # plan that survives it, which the check below proves.
            try:
                rows = set(_grammar.HASH_RE.findall(
                    read_plan_bytes(destination_path).decode("utf-8")
                ))
            except (BoardError, UnicodeError):
                continue
            if resume in rows:
                repairs.append(source)
        if not repairs:
            return 0
        stale_ids = {entity["id"] for entity in repairs}
        payload["entities"] = [
            entity for entity in payload["entities"] if entity["id"] not in stale_ids
        ]
        used_projects = {entity["project"] for entity in payload["entities"]}
        payload["projects"] = [
            project for project in payload["projects"] if project["id"] in used_projects
        ]
        payload["projects"].sort(key=lambda item: (item["priority"], item["id"]))
        payload["entities"].sort(key=lambda item: (item["project"], item["id"]))
        payload["revision"] += 1
        _validate(payload)
        _write_and_commit(
            root, path, payload, "shadow board: discard missing unclaimed alias"
        )
        return len(repairs)
