#!/usr/bin/env python3
"""One local, privately journaled board for this computer.

Entity plans keep milestone/checkpoint text, proof, and evidence under the
private Shadow home. This file stores only project priority, entity-plan
locators and resume checkpoints, and claims. It never becomes a second task
authority or a source-controlled queue.
"""

from __future__ import annotations

from contextlib import contextmanager
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
from typing import Iterator
from urllib.parse import unquote, urlsplit

from shadow_scrub_lib import PRIVATE_PATH_RE, SECRET_SHAPE_RE
import shadow_plan_grammar as _grammar
import shadow_plan_store as _plan_store


SCHEMA = "shadow.root-board.v1"
DEFAULT_CLAIM_HOURS = 8
COMPLETION_RESERVATION_MINUTES = 10
RECOVERY_ACTION = "probe-proof-then-adopt-park-or-close"
ROW_ID = _grammar.ROW_ID_RE
ENTITY_ID = re.compile(r"[0-9a-f]{64}")
PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{1,31}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
BOARD_NAME = "board.json"
LOCK_NAME = ".board.lock"
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


class AlreadyClaimed(BoardError):
    def __init__(self, owner: str):
        super().__init__(f"claimed by {owner}")
        self.owner = owner


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
    origin = _git(repo, "config", "--get", "remote.origin.url")
    if origin.returncode == 0 and origin.stdout.strip():
        identity = normalized_origin(origin.stdout.strip())
        remote_name = identity.rstrip("/").rsplit("/", 1)[-1]
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
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(command, 124, "", str(exc))


def _git_marker(path: Path) -> Path | None:
    cursor = Path(os.path.abspath(path))
    while cursor.parent != cursor:
        marker = cursor / ".git"
        if marker.exists() or marker.is_symlink():
            return marker
        cursor = cursor.parent
    return None


def normalized_origin(origin: str) -> str:
    """Return one offline identity for common Git remote spellings."""
    if not origin:
        return ""
    text = origin.strip()
    if "://" in text:
        parsed = urlsplit(text)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port == {"ssh": 22, "https": 443, "http": 80, "git": 9418}.get(scheme):
            port = None
        authority = host + (f":{port}" if port is not None else "")
        path = parsed.path.rstrip("/").removesuffix(".git")
        return authority + path
    # SCP-style and local remotes are not URL-parsed, but query/fragment data
    # is still never identity or display data. In particular, credential query
    # parameters must not enter board ids, status, or browser JSON.
    text = text.split("#", 1)[0].split("?", 1)[0]
    text = text.rstrip("/").removesuffix(".git")
    text = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", text)
    text = re.sub(r"^[^/@]+@", "", text)
    text = re.sub(r"^([^/:]+):(?!/)", r"\1/", text)
    host, slash, path = text.partition("/")
    return host.lower() + slash + path


def normalized_repo_origin(repo: Path, origin: str) -> str:
    """Normalize a configured remote, resolving filesystem forms at the repo."""
    raw = origin.strip()
    if not raw:
        return ""
    if raw.lower().startswith("file://"):
        parsed = urlsplit(raw)
        return f"local-remote:{Path(unquote(parsed.path)).resolve()}"
    if "://" in raw or re.match(r"^[^/@:]+@?[^/:]+:(?!/)", raw):
        return normalized_origin(raw)
    local = Path(raw).expanduser()
    if not local.is_absolute():
        local = repo / local
    return f"local-remote:{local.resolve()}"


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


def origin_of(repo: Path) -> str:
    marker = _git_marker(repo)
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    origin = (
        normalized_repo_origin(repo, result.stdout.strip())
        if result is not None and result.returncode == 0
        else ""
    )
    if origin:
        return origin
    # Linked worktrees share one common Git directory even when the repository
    # has no remote.  The checkout path does not: using it let two worktrees of
    # one local repository both claim the same logical row.
    try:
        common = subprocess.run(
            [
                "git", "-C", str(repo), "rev-parse", "--path-format=absolute",
                "--git-common-dir",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        common = None
    if common is not None and common.returncode == 0 and common.stdout.strip():
        common_path = Path(common.stdout.strip())
        if not common_path.is_absolute():
            common_path = repo / common_path
        return f"local-git:{common_path.resolve()}"
    if marker is not None:
        raise BoardError("project Git identity could not be read; retry when Git is available")
    return str(repo.resolve())


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
    """Return a stable human locator without exposing an absolute home path."""
    candidate = Path(os.path.abspath(plan))
    try:
        result = subprocess.run(
            ["git", "-C", str(candidate.parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is None or result.returncode or not result.stdout.strip():
        public = f"{candidate.parent.name}/PLAN.md"
        if SECRET_SHAPE_RE.search(public) or PRIVATE_PATH_RE.search(public):
            digest = hashlib.sha256(public.encode("utf-8")).hexdigest()[:8]
            return f"entity@{digest}/PLAN.md"
        return public
    repo = Path(result.stdout.strip()).resolve()
    try:
        relative = candidate.relative_to(repo).as_posix()
    except ValueError:
        relative = candidate.name
    origin = origin_of(repo)
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


def plan_mtime(repo: Path) -> float:
    try:
        return (repo / "PLAN.md").stat().st_mtime
    except OSError:
        return 0.0


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


def plan_identity_parts(plan: Path, *, require_regular: bool = False) -> tuple[str, str]:
    """Resolve logical identity fields without reading the PLAN.md body."""
    if require_regular and not regular_plan(plan):
        raise BoardError("entity identity requires a regular, non-symlink PLAN.md")
    plan = Path(os.path.abspath(plan))
    local_root = _local_plan_root_containing(plan)
    if local_root is not None:
        try:
            return f"local-plan:{local_root}", plan.resolve().relative_to(local_root).as_posix()
        except (OSError, ValueError) as exc:
            raise BoardError("local plan identity could not be read") from exc
    marker = _git_marker(plan.parent)
    result = _git(plan.parent, "rev-parse", "--show-toplevel")
    if result.returncode == 0 and result.stdout.strip():
        repo = Path(result.stdout.strip()).resolve()
        try:
            relative = plan.relative_to(repo).as_posix()
        except ValueError:
            try:
                relative = (plan.parent.resolve() / plan.name).relative_to(repo).as_posix()
            except ValueError:
                relative = plan.name
    elif marker is not None:
        raise BoardError("project Git identity could not be read; retry when Git is available")
    else:
        repo, relative = plan.parent, plan.name
    return origin_of(repo), relative


def entity_id(plan: Path) -> str:
    """Logical entity identity: normalized origin plus repository-relative path."""
    return logical_entity_id(*plan_identity_parts(plan, require_regular=True))


def logical_entity_id(origin: str, relative: str) -> str:
    """Hash the logical identity already resolved by bounded discovery."""
    logical = f"{origin}\0{relative}".encode("utf-8")
    return hashlib.sha256(logical).hexdigest()


def head_plan_snapshot(plan: Path) -> tuple[dict[str, str], bytes]:
    """Return the exact PLAN bytes stored at HEAD, independent of worktree dirt."""
    if not regular_plan(plan):
        raise BoardError("entity plan must be a regular, non-symlink PLAN.md")
    plan = plan.resolve()
    top = _git(plan.parent, "rev-parse", "--show-toplevel")
    if top.returncode or not top.stdout.strip():
        raise BoardError("entity plan must be committed in a Git repository")
    repo = Path(top.stdout.strip()).resolve()
    try:
        relative = plan.relative_to(repo).as_posix()
    except ValueError as exc:
        raise BoardError("entity plan is outside its Git repository") from exc
    head = _git(repo, "rev-parse", "HEAD")
    blob = _git(repo, "rev-parse", f"HEAD:{relative}")
    if head.returncode or blob.returncode:
        raise BoardError("entity plan is not present at the current Git HEAD")
    try:
        frozen = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "blob", blob.stdout.strip()],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BoardError("entity plan HEAD bytes could not be frozen") from exc
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


def committed_plan_snapshot(plan: Path) -> tuple[dict[str, str], bytes]:
    """Return worktree bytes and the exact Git object that serves them, or refuse."""
    token, _ = head_plan_snapshot(plan)
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
        hashed = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "--stdin"],
            input=root_content,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise BoardError("entity plan bytes could not be frozen") from exc
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


def frozen_plan_snapshot(plan: Path, *, home: Path | None = None) -> tuple[dict[str, str], bytes]:
    """Freeze either a product's committed plan or one local-only plan.

    Product repositories remain free to keep a release plan with their source.
    Shadow, ``ai``, and ``ai-leo`` operational plans are deliberately different:
    their authority lives below ``~/.shadow/plans`` and is never committed.
    """
    if not is_local_plan(plan, home=home):
        return committed_plan_snapshot(plan)
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


def _validate(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "revision", "projects", "entities", "claims"
    }:
        raise BoardError("board has unknown or missing top-level fields")
    if payload["schema"] != SCHEMA:
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


def _decode(path: Path) -> dict:
    if path.is_symlink():
        raise BoardError("board file must not be a symlink")
    try:
        return _validate(json.loads(path.read_text(encoding="utf-8")))
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


def _write(path: Path, payload: dict) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".board.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
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


def _initialize_git(root: Path) -> None:
    """Maintain a private crash-recovery journal for board pointers only."""
    git_dir = root / ".git"
    if git_dir.is_symlink() or (git_dir.exists() and not git_dir.is_dir()):
        raise BoardError("root board Git directory must not be a symlink or file")
    result = subprocess.run(
        ["git", "init", "--quiet", str(root)], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise BoardError("root board Git repository could not be initialized")
    index_lock = git_dir / "index.lock"
    if index_lock.exists() or index_lock.is_symlink():
        if index_lock.is_symlink() or not index_lock.is_file():
            raise BoardError("root board Git receipt lock is unsafe")
        index_lock.unlink()
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
                    payload = _validate(json.loads(historical.stdout))
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


def entity_state_by_id(identity: str, *, home: Path | None = None) -> dict | None:
    """Resolve a board-issued entity id, refusing stale ids after identity moves."""
    resolved = resolve_entity(identity, home=home)
    return resolved["state"] if resolved is not None else None


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


def canonical_plan_by_id(identity: str, *, home: Path | None = None) -> Path:
    """Return the regular canonical pointer for one current board entity id."""
    return canonical_plan_by_id_at_revision(identity, home=home)


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
        if winner is not None:
            if not adopt_expired or not claim_is_stale(winner, now=claimed):
                raise AlreadyClaimed(winner["owner"])
            # Adoption is an explicit compare-and-swap under the same lock as
            # the fresh read.  It never silently reassigns a live claim.
            payload["claims"].remove(winner)
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
        payload["claims"].append(claim_record)
        payload["projects"].sort(key=lambda item: (item["priority"], item["id"]))
        payload["entities"].sort(key=lambda item: (item["project"], item["id"]))
        payload["claims"].sort(key=lambda item: (item["entity"], item["row"]))
        payload["revision"] += 1
        _validate(payload)
        _write(path, payload)
        _commit(root, f"shadow board: claim {row}")
        snapshot = json.loads(json.dumps(payload))
        return {
            "payload": snapshot,
            "entity": next(item for item in snapshot["entities"] if item["id"] == identity),
            "claim": next(
                item
                for item in snapshot["claims"]
                if (item["entity"], item["row"], item["owner"])
                == (identity, row, owner)
            ),
        }


def reconcile(
    entities: list[dict],
    legacy_claims: list[dict],
    *,
    retired_entities: list[str] | None = None,
    retired_sources: list[dict] | None = None,
    home: Path | None = None,
) -> dict:
    """Atomically import bounded discovery into pointer-only local authority.

    Discovery may add an entity or repair a missing locator. It never replaces
    a healthy canonical locator, project priority, or that entity's resume with
    metadata from a sibling checkout. Historical plan claims are consumed once.
    """
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
                raise BoardError(
                    "bounded discovery entity changed during reconciliation; retry"
                ) from exc
            try:
                assert_hot_plan_budget(content)
            except BoardError as exc:
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
        assert_seed_content()
        assert_repair_states()
        assert_seed_witnesses()
        assert_retired_content()
        original_payload = json.loads(json.dumps(payload))
        changed = False
        identity_index = _identity_index(payload)
        prepared_by_id = {seed["id"]: seed for seed in prepared}
        original_entities = json.loads(json.dumps(payload["entities"]))
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
                changed = True

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
        if payload["entities"] != original_entities or payload["claims"] != original_claims:
            changed = True
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
                payload["claims"].append(
                    {
                        "entity": identity,
                        "row": row,
                        "owner": owner,
                        "claimed_at": _stamp(claimed_at),
                        "return_by": _stamp(
                            claimed_at + timedelta(hours=DEFAULT_CLAIM_HOURS)
                        ),
                        "recovery": RECOVERY_ACTION,
                    }
                )
                changed = True
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
                changed = True

        used_projects = {entity["project"] for entity in payload["entities"]}
        if any(project["id"] not in used_projects for project in payload["projects"]):
            payload["projects"] = [
                project for project in payload["projects"] if project["id"] in used_projects
            ]
            changed = True

        payload["projects"].sort(key=lambda item: (item["priority"], item["id"]))
        payload["entities"].sort(key=lambda item: (item["project"], item["id"]))
        payload["claims"].sort(key=lambda item: (item["entity"], item["row"]))
        assert_seed_content()
        assert_repair_states()
        assert_seed_witnesses()
        assert_retired_content()
        if payload == original_payload:
            return json.loads(json.dumps(payload))
        payload["revision"] = original_payload["revision"] + 1
        _validate(payload)
        _write(path, payload)
        _commit(root, "shadow board: reconcile bounded portfolio")
        return json.loads(json.dumps(payload))


def _release_state(plan: Path, row: str, reason: str, *, text: str | None = None) -> None:
    if text is None:
        try:
            text = read_plan_text(plan)
        except BoardError as exc:
            raise BoardError("claim return needs a readable entity plan") from exc
    row_matches = []
    for line in text.splitlines():
        match = re.match(
            r"^- \[(pending|in_progress|blocked|completed)] .+? "
            r"(?P<id>~[0-9a-z]{4})(?: \(DoD\))?(?: \| .*)?$",
            line,
        )
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


def _reserve_claim_receipt(
    plan: Path,
    row: str,
    owner: str,
    *,
    expected_plan: dict[str, str] | None = None,
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
        if claim["owner"] != owner:
            raise BoardError(f"claim is owned by {claim['owner']}")
        if protect_until is not None:
            protected = protect_until.astimezone(timezone.utc)
            if _timestamp(claim["return_by"], "claim return-by") < protected:
                claim["return_by"] = _stamp(protected)
                payload["revision"] += 1
                _validate(payload)
                _write(path, payload)
                _commit(root, f"shadow board: reserve completion {row}")
        receipt = json.loads(json.dumps(claim))
        receipt["revision"] = payload["revision"]
        return receipt


def reserve_completion(
    plan: Path,
    row: str,
    owner: str,
    *,
    expected_plan: dict[str, str],
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
        if expected_claim is not None:
            claim_fields = {
                key: expected_claim.get(key)
                for key in ("entity", "row", "owner", "claimed_at", "return_by", "recovery")
            }
            if claim is None or any(claim.get(key) != value for key, value in claim_fields.items()):
                raise BoardError("claim changed before completion could close it; reconcile the proven row")
        if claim is not None and owner != claim["owner"]:
            raise BoardError(f"claim is owned by {claim['owner']}")
        if claim is not None:
            _release_state(plan, row, reason, text=expected_text)
        kept = [item for item in payload["claims"] if item is not claim]
        had_claim = len(kept) != len(payload["claims"])
        if claim is None:
            # A repeated owner return after the atomic close is a no-op. There
            # is no live claim to steal and no half-written resume state to
            # repair because both changed in the same board transaction.
            return json.loads(json.dumps(payload)), False
        if entity["plan"] != str(plan) and not regular_plan(Path(entity["plan"])):
            entity["plan"] = str(plan)
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
        _write(path, payload)
        _commit(root, f"shadow board: release {row}")
        return json.loads(json.dumps(payload)), True


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
        _write(path, payload)
        _commit(root, f"shadow board: set project priority {priority}")
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
        _write(path, payload)
        _commit(root, "shadow board: move authority to local plan")
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
        _write(path, payload)
        _commit(root, "shadow board: remove stale source alias")
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
        _write(path, payload)
        _commit(root, "shadow board: discard missing unclaimed alias")
        return len(repairs)


def claimed_rows(plan: Path, *, home: Path | None = None) -> set[str]:
    state = entity_state(plan, home=home)
    return (
        {item["row"] for item in state["claims"]}
        if state is not None and state["entity"] is not None
        else set()
    )
