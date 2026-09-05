#!/usr/bin/env python3
"""Shadow-managed worktree provenance, cleanup preview, and safe Trash lifecycle.

A worktree is eligible only when Shadow itself created it, the creation's
pending-to-issued journal authenticates the immutable receipt, and every
terminal/clean/landed/ownership/process predicate is still true.  Apply and
restore are journaled, inode-preserving Trash moves; there is no hard-delete,
force, worktree-remove, or prune path.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as _board  # noqa: E402
import shadow_git as _shadow_git  # noqa: E402


CREATION_SCHEMA = "shadow.worktree-creation.v1"
ISSUANCE_SCHEMA = "shadow.worktree-issuance.v1"
CLEAN_MANIFEST_SCHEMA = "shadow.clean-manifest.v1"
MAX_BYTES = 64 * 1024
REF_RE = re.compile(r"^refs/(?:heads|tags)/[-A-Za-z0-9._/]+$")
OID_RE = re.compile(r"^[0-9a-f]{40,64}$")
ROW_RE = re.compile(r"^~[0-9a-z]{4}$")
MANIFEST_ID_RE = re.compile(r"^manifest@([0-9a-f]{12})$")
WORKTREE_ID_RE = re.compile(r"^worktree@([0-9a-f]{12})$")
TRASH_RECEIPT_SCHEMA = "shadow.clean-trash-receipt.v1"
TRASH_JOURNAL_SCHEMA = "shadow.clean-trash-journal.v1"
RESTORE_JOURNAL_SCHEMA = "shadow.clean-restore-journal.v1"
AUTOMATIC_SCHEMA = "shadow.clean-automatic.v1"
AUTOMATIC_RUN_SCHEMA = "shadow.clean-automatic-run.v1"


class CleanError(ValueError):
    """A provenance or preview request is unsafe or stale."""


class CleanMoveCommittedError(CleanError):
    """The no-replace rename committed, but a post-rename sync failed."""


def _public_reason(value: str) -> str:
    """Return bounded reason text; Git stderr and private paths never cross CLI."""
    known = (
        "manifest expired", "manifest changed", "not Shadow-created", "active claim",
        "checkpoint is not terminal", "worktree is dirty", "untracked files",
        "ignored files", "submodule", "process holds", "process inspection unavailable",
        "primary worktree", "work is not landed", "changed since preview", "worktree changed after lock",
        "registration changed", "symlink", "Trash artifact",
        "Trash destination", "worktree lock", "already locked", "registration",
        "restore artifact", "restore journal", "original path", "same device",
        "recovery required", "source race", "private cleanup", "private restore", "payload changed",
        "content changed",
        "mutually exclusive",
    )
    for marker in known:
        if marker in value:
            return marker
    return "operation refused"


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _journal_digest(journal: dict[str, Any]) -> str:
    """Digest the immutable issuance intent, excluding transaction state."""
    return canonical_sha256(
        {key: value for key, value in journal.items() if key not in {"state", "receipt_sha256"}}
    )


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CleanError("timestamp must be an RFC3339 UTC timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise CleanError("timestamp must be an RFC3339 UTC timestamp") from exc


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _root(home: Path | None = None) -> Path:
    base = (home or Path.home()).resolve()
    root = base / ".shadow"
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise CleanError("private Shadow root is unsafe")
    return root


def _clean_dirs(home: Path | None = None, *, create: bool = False) -> dict[str, Path]:
    root = _root(home) / "clean"
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise CleanError("private clean root is unsafe")
    result = {name: root / name for name in (
        "receipts", "journals", "manifests", "trash-journals", "trash-receipts", "restore-journals",
    )}
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        for path in result.values():
            path.mkdir(mode=0o700, exist_ok=True)
            if path.is_symlink() or not path.is_dir():
                raise CleanError("private clean directory is unsafe")
            os.chmod(path, 0o700)
    return result


def _read(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise CleanError("private clean record is not a regular file")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise CleanError("private clean record must use mode 0600")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise CleanError("private clean record has the wrong owner")
        data = os.read(descriptor, MAX_BYTES + 1)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise CleanError("private clean record could not be read safely") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(data) > MAX_BYTES:
        raise CleanError("private clean record exceeds its bounded size")
    if (metadata.st_ino, metadata.st_dev, metadata.st_size, metadata.st_mtime_ns, metadata.st_mode, metadata.st_uid) != (
        after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns, after.st_mode, after.st_uid
    ):
        raise CleanError("private clean record changed while being read")
    return data


def _exclusive(path: Path, value: dict[str, Any]) -> None:
    encoded = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise CleanError("clean receipt already exists and is immutable") from exc
    except OSError as exc:
        raise CleanError("clean receipt could not be written exclusively") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise CleanError("clean receipt directory could not be synchronized") from exc


def _replace(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}")
    encoded = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    try:
        if path.exists() or path.is_symlink():
            _read(path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise CleanError("clean issuance journal could not be updated safely") from exc


def _automatic_path(home: Path | None = None) -> Path:
    """Return the computer-local automatic-cleanup preference path."""
    return _root(home) / "clean" / "automatic.json"


def _automatic_value(home: Path | None = None) -> bool:
    """Read the opt-in preference without creating any private state.

    Absence is the safe default.  If present, the record is authenticated by
    the same no-follow, owner, mode, bounded-read checks as other private
    records, and its schema is deliberately tiny so future fields cannot
    silently widen the cleanup authority.
    """
    path = _automatic_path(home)
    if not path.exists() and not path.is_symlink():
        return False
    try:
        value = json.loads(_read(path))
    except (CleanError, OSError, json.JSONDecodeError) as exc:
        raise CleanError("automatic cleanup preference is malformed") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "automatic_trash"}
        or value.get("schema") != AUTOMATIC_SCHEMA
        or not isinstance(value.get("automatic_trash"), bool)
    ):
        raise CleanError("automatic cleanup preference is malformed")
    return value["automatic_trash"]


def _write_automatic(value: bool, *, home: Path | None = None) -> bool:
    """Atomically set the local opt-in, returning whether bytes changed."""
    path = _automatic_path(home)
    clean_root = path.parent
    if clean_root.exists() and (clean_root.is_symlink() or not clean_root.is_dir()):
        raise CleanError("private clean root is unsafe")
    clean_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(clean_root, 0o700)
    desired = {"schema": AUTOMATIC_SCHEMA, "automatic_trash": value}
    if path.exists() or path.is_symlink():
        if _automatic_value(home) == value:
            return False
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}")
    encoded = (json.dumps(desired, sort_keys=True, indent=2) + "\n").encode()
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        _fsync_directory(clean_root)
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except OSError:
            pass
        raise CleanError("automatic cleanup preference could not be written safely") from exc
    return True


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env=_shadow_git.sanitized_git_env(),
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "Git command failed"
        raise CleanError(detail)
    return result


def _real_absolute(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise CleanError(f"{label} must be an absolute path")
    raw = Path(os.path.abspath(path))
    cursor = raw
    while cursor != cursor.parent:
        if cursor.is_symlink():
            # macOS exposes /tmp as the stable symlink alias /private/tmp.
            # Normalize that OS-owned alias, while refusing every
            # user-controlled symlink component.
            if cursor not in {Path("/tmp"), Path("/var")}:
                raise CleanError(f"{label} must not contain a symlink")
        cursor = cursor.parent
    return raw.resolve(strict=False)


def _claim_payload(
    payload: dict[str, Any], entity: str, checkpoint: str, seat: str,
    *, source: Path | None = None, locked_plan: Path | None = None,
) -> dict[str, Any]:
    if _board.ENTITY_ID.fullmatch(entity) is None:
        raise CleanError("entity must be one exact board identity")
    if ROW_RE.fullmatch(checkpoint) is None:
        raise CleanError("checkpoint must be one canonical row id")
    if payload is None:
        raise CleanError("exact live claim is required")
    entity_record = next((item for item in payload["entities"] if item["id"] == entity), None)
    if entity_record is None:
        raise CleanError("entity is not registered on this computer")
    if locked_plan is not None and Path(entity_record["plan"]).resolve() != locked_plan.resolve():
        raise CleanError("entity plan changed while creation was locked")
    if source is not None:
        try:
            declared = _board.origin_of(Path(entity_record["plan"]).parent)
            observed = _source_identity(source)
        except (_board.BoardError, CleanError) as exc:
            raise CleanError(str(exc)) from None
        if declared != observed:
            raise CleanError("source checkout does not share the entity source identity")
    claim = next(
        (
            item
            for item in payload["claims"]
            if item["entity"] == entity and item["row"] == checkpoint and item["owner"] == seat
        ),
        None,
    )
    if claim is None:
        raise CleanError("exact live claim is required")
    if _board.claim_is_stale(claim):
        raise CleanError("exact live claim is expired")
    return claim


def _claim(home: Path, entity: str, checkpoint: str, seat: str, *, source: Path | None = None) -> dict[str, Any]:
    try:
        _board.validate_owner(seat)
        payload = _board.snapshot(home=home)
        return _claim_payload(payload, entity, checkpoint, seat, source=source)
    except _board.BoardError as exc:
        raise CleanError(str(exc)) from None


@contextmanager
def _locked_claim(
    home: Path, entity: str, checkpoint: str, seat: str, *, source: Path | None = None,
):
    """Hold the canonical project lock, then the canonical root-board CAS lock."""
    try:
        _board.validate_owner(seat)
        initial = _board.snapshot(home=home)
        _claim_payload(initial, entity, checkpoint, seat, source=source)
        entity_record = next(item for item in initial["entities"] if item["id"] == entity)
        plan = Path(entity_record["plan"]).resolve()
        with _board.project_lock(plan):
            with _board._transaction(home) as (_, _, payload):
                _claim_payload(payload, entity, checkpoint, seat, source=source, locked_plan=plan)
                yield
    except _board.BoardError as exc:
        raise CleanError(str(exc)) from None


def _source_identity(repo: Path) -> str:
    try:
        return _board.origin_of(repo)
    except _board.BoardError as exc:
        raise CleanError(str(exc)) from None


def _journal_value(
    *, source: Path, destination: Path, entity: str, checkpoint: str, seat: str,
    ref: str, landed_ref: str, nonce: str, created_at: str,
    source_head: str,
) -> dict[str, Any]:
    return {
        "schema": ISSUANCE_SCHEMA,
        "state": "pending",
        "nonce": nonce,
        "created_at": created_at,
        "source_repo": str(source),
        "destination": str(destination),
        "source_identity": _source_identity(source),
        "entity": entity,
        "checkpoint": checkpoint,
        "seat": seat,
        "ref": ref,
        "source_head": source_head,
        "landed_ref": landed_ref,
    }


def _creation_inputs(
    source_repo: Path,
    destination: Path,
    *,
    ref: str = "HEAD",
    landed_ref: str,
    now: str | datetime | None = None,
) -> tuple[Path, Path, str, str]:
    source = _real_absolute(Path(source_repo), "source repository")
    destination = _real_absolute(Path(destination), "worktree destination")
    if not REF_RE.fullmatch(landed_ref):
        raise CleanError("landed ref must be a safe full Git ref")
    if ref != "HEAD" and (not REF_RE.fullmatch(ref) and not OID_RE.fullmatch(ref)):
        raise CleanError("creation ref must be HEAD, a full Git ref, or a full object id")
    _git(source, "rev-parse", "--show-toplevel")
    if ref != "HEAD":
        _git(source, "check-ref-format", ref)
    source_head = _git(source, "rev-parse", ref).stdout.strip()
    if not OID_RE.fullmatch(source_head):
        raise CleanError("creation ref did not resolve to a full Git object id")
    stamp = _stamp(_utc(now) if now is not None else datetime.now(timezone.utc))
    return source, destination, source_head, stamp


def _prepare_creation_locked(
    source: Path,
    destination: Path,
    *,
    entity: str,
    checkpoint: str,
    seat: str,
    ref: str,
    landed_ref: str,
    source_head: str,
    stamp: str,
    home: Path | None = None,
) -> dict[str, Any]:
    directories = _clean_dirs(home, create=True)
    # A matching pending record is the only retry path.  No filesystem or Git
    # discovery is used to find a child worktree.
    for journal_path in sorted(directories["journals"].glob("*.json")):
        try:
            journal = json.loads(_read(journal_path))
        except (CleanError, json.JSONDecodeError):
            continue
        if not isinstance(journal, dict) or journal.get("state") != "pending":
            continue
        if journal.get("destination") == str(destination):
            expected = _journal_value(
                source=source, destination=destination, entity=entity,
                checkpoint=checkpoint, seat=seat, ref=ref,
                landed_ref=landed_ref, nonce=str(journal.get("nonce")),
                created_at=str(journal.get("created_at")), source_head=source_head,
            )
            if all(journal.get(key) == value for key, value in expected.items()):
                return {**journal, "journal_path": str(journal_path)}
            raise CleanError("pending issuance does not match this exact claim")
    if destination.exists() or destination.is_symlink():
        raise CleanError("worktree destination must be absent")
    nonce = secrets.token_hex(32)
    value = _journal_value(
        source=source, destination=destination, entity=entity,
        checkpoint=checkpoint, seat=seat, ref=ref, landed_ref=landed_ref,
        nonce=nonce, created_at=stamp, source_head=source_head,
    )
    journal_path = directories["journals"] / f"{nonce}.json"
    _exclusive(journal_path, value)
    return {**value, "journal_path": str(journal_path)}


def prepare_creation(
    source_repo: Path,
    destination: Path,
    *,
    entity: str,
    checkpoint: str,
    seat: str,
    ref: str = "HEAD",
    landed_ref: str,
    home: Path | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    """Reserve one managed worktree creation before invoking Git."""
    source, destination, source_head, stamp = _creation_inputs(
        source_repo, destination, ref=ref, landed_ref=landed_ref, now=now,
    )
    with _locked_claim(_root(home).parent, entity, checkpoint, seat, source=source):
        return _prepare_creation_locked(
            source, destination, entity=entity, checkpoint=checkpoint, seat=seat,
            ref=ref, landed_ref=landed_ref, source_head=source_head, stamp=stamp,
            home=home,
        )


def _receipt_from(journal: dict[str, Any], destination: Path, home: Path) -> dict[str, Any]:
    if not destination.is_dir() or destination.is_symlink():
        raise CleanError("created worktree is missing or unsafe")
    registered = _git(Path(journal["source_repo"]), "worktree", "list", "--porcelain").stdout
    registered_paths = {
        Path(line.removeprefix("worktree ")).resolve()
        for line in registered.splitlines()
        if line.startswith("worktree ")
    }
    if destination.resolve() not in registered_paths:
        raise CleanError("created worktree is not the exact registered child")
    head = _git(destination, "rev-parse", "HEAD").stdout.strip()
    common = _git(destination, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    admin = _git(destination, "rev-parse", "--path-format=absolute", "--git-dir").stdout.strip()
    if not OID_RE.fullmatch(head) or not common or not admin:
        raise CleanError("created worktree provenance could not be frozen")
    source_common = _git(Path(journal["source_repo"]), "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    if Path(common).resolve() != Path(source_common).resolve():
        raise CleanError("created worktree does not share the source Git store")
    metadata = os.lstat(destination)
    if not stat.S_ISDIR(metadata.st_mode):
        raise CleanError("created worktree is not a real directory")
    branch_probe = subprocess.run(
        ["git", "-C", str(destination), "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True, text=True, check=False, env=_shadow_git.sanitized_git_env(),
    )
    branch = branch_probe.stdout.strip() if branch_probe.returncode == 0 else None
    receipt = {
        "schema": CREATION_SCHEMA,
        "created_at": journal["created_at"],
        "worktree": {"path": str(destination), "device": metadata.st_dev, "inode": metadata.st_ino},
        "git": {"common_dir": str(Path(common).resolve()), "admin_dir": str(Path(admin).resolve())},
        "source": {"repository": journal["source_identity"]},
        "claim": {"entity": journal["entity"], "checkpoint": journal["checkpoint"], "seat": journal["seat"]},
        "initial": {"head": head, "ref": journal["ref"], "branch": branch, "detached": branch is None},
        "landed_ref": journal["landed_ref"],
        "nonce": journal["nonce"],
        "issuance_journal_sha256": _journal_digest(journal),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def _finish_creation_locked(
    nonce: str, *, home: Path | None = None, destination: Path | None = None,
) -> dict[str, Any]:
    directories = _clean_dirs(home, create=False)
    valid_ids = {created["receipt_sha256"] for created, _journal in _valid_records(home)}
    journal_path = directories["journals"] / f"{nonce}.json"
    journal = json.loads(_read(journal_path))
    if not isinstance(journal, dict) or journal.get("schema") != ISSUANCE_SCHEMA or journal.get("state") != "pending":
        raise CleanError("issuance journal is not a matching pending transaction")
    expected_destination = Path(journal["destination"])
    if destination is not None and _real_absolute(Path(destination), "worktree destination") != expected_destination:
        raise CleanError("pending issuance destination does not match")
    source = Path(journal["source_repo"])
    current = json.loads(_read(journal_path))
    if current != journal:
        raise CleanError("issuance journal changed while creation was waiting")
    destination = expected_destination
    if not destination.exists():
        command = ["worktree", "add", str(destination), journal["ref"]]
        _git(source, *command)
    receipt = _receipt_from(journal, destination, home or Path.home())
    if receipt["initial"]["head"] != journal.get("source_head"):
        raise CleanError("created worktree does not match the pending source ref")
    receipt_path = directories["receipts"] / f"{receipt['receipt_sha256']}.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        existing = json.loads(_read(receipt_path))
        if existing != receipt:
            raise CleanError("creation receipt already exists and changed")
    else:
        _exclusive(receipt_path, receipt)
    issued = {**journal, "state": "issued", "receipt_sha256": receipt["receipt_sha256"]}
    _replace(journal_path, issued)
    return {"state": "issued", "receipt_sha256": receipt["receipt_sha256"], "receipt_path": str(receipt_path), "journal_path": str(journal_path)}


def finish_creation(nonce: str, *, home: Path | None = None, destination: Path | None = None) -> dict[str, Any]:
    directories = _clean_dirs(home, create=False)
    journal_path = directories["journals"] / f"{nonce}.json"
    journal = json.loads(_read(journal_path))
    if not isinstance(journal, dict) or journal.get("schema") != ISSUANCE_SCHEMA or journal.get("state") != "pending":
        raise CleanError("issuance journal is not a matching pending transaction")
    source = Path(journal["source_repo"])
    with _locked_claim(_root(home).parent, journal["entity"], journal["checkpoint"], journal["seat"], source=source):
        return _finish_creation_locked(nonce, home=home, destination=destination)


def create_managed_worktree(
    source_repo: Path,
    destination: Path,
    *,
    entity: str,
    checkpoint: str,
    seat: str,
    ref: str = "HEAD",
    landed_ref: str,
    home: Path | None = None,
) -> dict[str, Any]:
    source, destination, source_head, stamp = _creation_inputs(
        source_repo, destination, ref=ref, landed_ref=landed_ref, now=None,
    )
    with _locked_claim(_root(home).parent, entity, checkpoint, seat, source=source):
        pending = _prepare_creation_locked(
            source, destination, entity=entity, checkpoint=checkpoint, seat=seat,
            ref=ref, landed_ref=landed_ref, source_head=source_head, stamp=stamp,
            home=home,
        )
        return _finish_creation_locked(pending["nonce"], home=home, destination=destination)


def _valid_records(home: Path | None = None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    directories = _clean_dirs(home, create=False)
    if not directories["receipts"].is_dir() or not directories["journals"].is_dir():
        return []
    records = []
    for receipt_path in sorted(directories["receipts"].glob("*.json")):
        try:
            receipt = json.loads(_read(receipt_path))
            if not isinstance(receipt, dict) or receipt.get("schema") != CREATION_SCHEMA:
                continue
            digest = receipt.get("receipt_sha256")
            if digest != canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"}):
                continue
            if receipt_path.name != f"{digest}.json":
                continue
            journal_path = directories["journals"] / f"{receipt.get('nonce')}.json"
            journal = json.loads(_read(journal_path))
            if journal.get("schema") != ISSUANCE_SCHEMA or journal.get("state") != "issued":
                continue
            if journal.get("receipt_sha256") != digest or journal.get("nonce") != receipt.get("nonce"):
                continue
            if receipt.get("issuance_journal_sha256") != _journal_digest(journal):
                # Old or hand-authored journals are not eligible.
                continue
            records.append((receipt, journal))
        except (CleanError, OSError, json.JSONDecodeError, TypeError, KeyError):
            continue
    return records


def _preview_refusal(receipt: dict[str, Any], journal: dict[str, Any], home: Path) -> str | None:
    """Run the same read-only predicates used by apply."""
    try:
        plan, _state = _terminal_checkpoint(home, receipt["claim"]["entity"], receipt["claim"]["checkpoint"])
        target = Path(receipt["worktree"]["path"])
        head = _git(target, "rev-parse", "HEAD").stdout.strip()
        metadata = target.lstat()
        _status, status_sha = _status_snapshot(target)
        tree_sha = _tree_snapshot(target)
        listing, _paths = _worktree_listing(Path(journal["source_repo"]))
        manifest = {
            "schema": CLEAN_MANIFEST_SCHEMA,
            "generated_at": _stamp(datetime.now(timezone.utc)),
            "expires_at": _stamp(datetime.now(timezone.utc) + timedelta(minutes=15)),
            "target": {
                "kind": "worktree", "path": str(target), "head": head,
                "landed_ref": receipt["landed_ref"], "device": metadata.st_dev,
                "inode": metadata.st_ino, "mode": metadata.st_mode,
                "mtime_ns": metadata.st_mtime_ns, "ctime_ns": metadata.st_ctime_ns,
                "status_sha256": status_sha,
                "worktree_listing_sha256": hashlib.sha256(listing.encode("utf-8")).hexdigest(),
                "worktree_listing_unlocked_sha256": _listing_without_lock_digest(listing),
                "tree_sha256": tree_sha,
            },
            "entity": receipt["claim"]["entity"], "checkpoint": receipt["claim"]["checkpoint"],
            "creation_receipt": receipt["receipt_sha256"],
            "issuance_journal": _journal_digest(journal),
            "lifecycle_target": {"kind": "worktree", "head": head, "landed_ref": receipt["landed_ref"]},
        }
        _target_snapshot(manifest, receipt, journal, home)
        return None
    except (CleanError, OSError, KeyError, TypeError, ValueError) as exc:
        return _public_reason(str(exc))


def preview(*, repo: Path | None = None, worktree: Path | None = None, home: Path | None = None) -> dict[str, Any]:
    """Return a zero-write public projection of issued Shadow worktrees."""
    narrowed = _real_absolute(Path(worktree), "worktree") if worktree is not None else None
    candidates: list[dict[str, Any]] = []
    refusals: list[dict[str, Any]] = []
    for receipt, journal in _valid_records(home):
        path = Path(receipt["worktree"]["path"])
        if narrowed is not None and path != narrowed:
            continue
        if repo is not None and Path(journal["source_repo"]).resolve() != _real_absolute(Path(repo), "repository"):
            continue
        reason = _preview_refusal(receipt, journal, (home or Path.home()).resolve())
        candidate = {
            "id": f"worktree@{receipt['receipt_sha256'][:12]}",
            "state": "eligible" if reason is None else "refused",
            "reason": "eligible" if reason is None else reason,
            "entity": receipt["claim"]["entity"],
            "checkpoint": receipt["claim"]["checkpoint"],
        }
        # `candidates` remains the historical public collection for callers
        # that enumerate managed worktrees; refusals are explicit and never
        # imply apply eligibility.
        candidates.append(candidate)
        if reason is not None:
            refusals.append({"id": candidate["id"], "reason": reason})
    report: dict[str, Any] = {
        "schema": "shadow.clean-preview.v1",
        "action": "preview",
        "changed": False,
        "explanation": "preview is zero-write; no repository, board, plan, manifest, Git, or Trash state changes",
        "candidates": candidates,
        "refusals": refusals,
    }
    if narrowed is not None and not candidates:
        report["reason"] = "not Shadow-created"
    return report


def automatic_status(*, home: Path | None = None) -> dict[str, Any]:
    """Project the computer-local automatic Trash preference."""
    return {
        "schema": AUTOMATIC_SCHEMA,
        "action": "status",
        "automatic_trash": _automatic_value(home),
        "changed": False,
    }


def run_automatic_cleanup(
    repo: Path,
    *,
    home: Path | None = None,
    trash_root: Path | None = None,
    entity: str | None = None,
    checkpoint: str | None = None,
) -> dict[str, Any]:
    """Perform one lifecycle-bound cleanup pass when the computer opted in.

    The pass deliberately has no retry loop.  Each receipt is previewed,
    prepared into a fresh manifest, and handed to the existing strict apply
    transaction at most once.  Reports contain only opaque worktree ids and
    bounded reason labels; paths and provider/private records never cross the
    lifecycle boundary.
    """
    if not _automatic_value(home):
        return {
            "schema": AUTOMATIC_RUN_SCHEMA,
            "action": "automatic_cleanup",
            "enabled": False,
            "changed": False,
            "candidates": [],
        }
    source = _real_absolute(Path(repo), "repository")
    candidates: list[dict[str, Any]] = []
    for receipt, journal in _valid_records(home):
        if Path(journal["source_repo"]).resolve() != source:
            continue
        claim = receipt.get("claim") or {}
        if entity is not None and claim.get("entity") != entity:
            continue
        if checkpoint is not None and claim.get("checkpoint") != checkpoint:
            continue
        worktree_id = f"worktree@{receipt['receipt_sha256'][:12]}"
        base = {
            "id": worktree_id,
            "entity": claim.get("entity"),
            "checkpoint": claim.get("checkpoint"),
        }
        try:
            refusal = _preview_refusal(receipt, journal, (home or Path.home()).resolve())
            if refusal is not None:
                candidates.append({**base, "state": "refused", "reason": refusal})
                continue
            target = receipt["worktree"]
            prepared = prepare_manifest(
                {
                    "worktree": {
                        "path": target["path"],
                        "head": receipt["initial"]["head"],
                        "landed_ref": receipt["landed_ref"],
                    },
                    "entity": claim["entity"],
                    "checkpoint": claim["checkpoint"],
                    "creation_receipt": receipt["receipt_sha256"],
                    "issuance_journal": receipt["issuance_journal_sha256"],
                },
                home=home,
            )
            applied = apply_manifest(
                prepared["id"],
                expected_sha256=prepared["cas"],
                home=home,
                trash_root=trash_root,
            )
            candidates.append({
                **base,
                "state": applied.get("action", "applied"),
                "changed": bool(applied.get("changed", False)),
            })
        except Exception as exc:  # one candidate must not block the pass
            # Do not expose exception text from Git, filesystem, or private
            # records.  _public_reason is an allowlisted opaque vocabulary.
            candidates.append({
                **base,
                "state": "refused",
                "reason": _public_reason(str(exc)),
            })
    return {
        "schema": AUTOMATIC_RUN_SCHEMA,
        "action": "automatic_cleanup",
        "enabled": True,
        "changed": any(item.get("changed", False) for item in candidates),
        "candidates": candidates,
    }


def lifecycle_summaries(*, home: Path | None = None) -> list[dict[str, Any]]:
    """Project authenticated managed-worktree lifecycle without private data.

    This is intentionally a read-only join for browser projections: paths,
    Git refs, CAS values, source identities, and receipt locations never cross
    this boundary.
    """
    summaries_by_id = {}
    private_home = (home or Path.home()).resolve()
    for receipt, journal in _valid_records(home):
        worktree_id = f"worktree@{receipt['receipt_sha256'][:12]}"
        refusal = _preview_refusal(receipt, journal, private_home)
        summaries_by_id[worktree_id] = {
            "id": worktree_id,
            "state": "issued" if refusal is None else "noneligible",
            "entity": receipt["claim"]["entity"],
            "checkpoint": receipt["claim"]["checkpoint"],
        }
    directories = _clean_dirs(home, create=False)
    valid_ids = {created["receipt_sha256"] for created, _journal in _valid_records(home)}
    if directories["trash-receipts"].is_dir():
        for path in sorted(directories["trash-receipts"].glob("*.json")):
            try:
                receipt = json.loads(_read(path))
            except (CleanError, OSError, json.JSONDecodeError):
                continue
            if not isinstance(receipt, dict) or receipt.get("schema") != TRASH_RECEIPT_SCHEMA:
                continue
            worktree_id = receipt.get("worktree_id")
            if not isinstance(worktree_id, str) or WORKTREE_ID_RE.fullmatch(worktree_id) is None:
                continue
            try:
                if receipt.get("creation_receipt") not in valid_ids:
                    continue
                authenticated, _path = _load_trash_receipt(worktree_id, private_home)
            except (CleanError, KeyError, TypeError):
                continue
            summaries_by_id[worktree_id] = {
                "id": worktree_id,
                "state": authenticated.get("state", "trashed"),
                "entity": authenticated["entity"],
                "checkpoint": authenticated["checkpoint"],
            }
    return [summaries_by_id[key] for key in sorted(summaries_by_id)]


# Browser projection consumers use the singular name; keep the descriptive
# plural as an internal spelling-compatible alias.
lifecycle_summary = lifecycle_summaries


def _manifest_payload(candidate: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    target = candidate.get("target") or candidate.get("worktree")
    if not isinstance(target, dict):
        raise CleanError("manifest target is missing")
    path = target.get("path")
    head = target.get("head")
    landed_ref = target.get("landed_ref") or candidate.get("landed_ref")
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise CleanError("manifest target path must be absolute")
    path = str(_real_absolute(Path(path), "manifest target"))
    if not isinstance(head, str) or not OID_RE.fullmatch(head):
        raise CleanError("manifest target head must be one full Git object id")
    if not isinstance(landed_ref, str) or not REF_RE.fullmatch(landed_ref):
        raise CleanError("manifest landed ref must be one safe full Git ref")
    entity = candidate.get("entity") or (candidate.get("claim") or {}).get("entity")
    checkpoint = candidate.get("checkpoint") or (candidate.get("claim") or {}).get("checkpoint")
    receipt = candidate.get("creation_receipt") or candidate.get("receipt_sha256")
    journal = candidate.get("issuance_journal") or candidate.get("issuance_journal_sha256")
    if not isinstance(entity, str) or _board.ENTITY_ID.fullmatch(entity) is None:
        raise CleanError("manifest entity is invalid")
    if not isinstance(checkpoint, str) or ROW_RE.fullmatch(checkpoint) is None:
        raise CleanError("manifest checkpoint is invalid")
    if not isinstance(receipt, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt):
        raise CleanError("manifest creation receipt digest is invalid")
    if not isinstance(journal, str) or not re.fullmatch(r"[0-9a-f]{64}", journal):
        raise CleanError("manifest issuance journal digest is invalid")
    target_payload: dict[str, Any] = {"kind": "worktree", "path": path, "head": head, "landed_ref": landed_ref}
    # Actual prepare calls add an exact filesystem/Git CAS. Keep accepting
    # the older design-only payload shape so read-only callers cannot turn a
    # synthetic example into an apply-capable manifest.
    for key in ("device", "inode", "mode", "mtime_ns", "ctime_ns", "status_sha256", "worktree_listing_sha256", "worktree_listing_unlocked_sha256", "tree_sha256"):
        if key in target:
            target_payload[key] = target[key]
    return {
        "schema": CLEAN_MANIFEST_SCHEMA,
        "generated_at": _stamp(now),
        "expires_at": _stamp(now + timedelta(minutes=15)),
        "target": target_payload,
        "entity": entity,
        "checkpoint": checkpoint,
        "creation_receipt": receipt,
        "issuance_journal": journal,
        "lifecycle_target": {"kind": "worktree", "head": head, "landed_ref": landed_ref},
    }


def _prepare_manifest_record(
    candidate: dict[str, Any], *, home: Path | None = None, now: str | datetime | None = None,
) -> tuple[Path, dict[str, Any], str]:
    directories = _clean_dirs(home, create=True)
    current = _utc(now) if now is not None else datetime.now(timezone.utc)
    enriched = dict(candidate)
    target = dict(candidate.get("target") or candidate.get("worktree") or {})
    try:
        target_path = Path(target["path"])
        if target_path.is_dir() and not target_path.is_symlink():
            metadata = target_path.lstat()
            target.update({
                "device": metadata.st_dev,
                "inode": metadata.st_ino,
                "mode": metadata.st_mode,
                "mtime_ns": metadata.st_mtime_ns,
                "ctime_ns": metadata.st_ctime_ns,
            })
            _status, status_sha = _status_snapshot(target_path)
            target["status_sha256"] = status_sha
            target["tree_sha256"] = _tree_snapshot(target_path)
            source = None
            wanted = candidate.get("creation_receipt") or candidate.get("receipt_sha256")
            for receipt, journal in _valid_records(home):
                if receipt.get("receipt_sha256") == wanted:
                    source = Path(journal["source_repo"])
                    break
            if source is not None:
                listing, _paths = _worktree_listing(source)
                target["worktree_listing_sha256"] = hashlib.sha256(listing.encode("utf-8")).hexdigest()
                target["worktree_listing_unlocked_sha256"] = _listing_without_lock_digest(listing)
    except (CleanError, OSError, KeyError, subprocess.SubprocessError):
        # Synthetic design callers remain preview-only; apply requires the
        # complete target CAS and will refuse this payload explicitly.
        pass
    enriched["target"] = target
    payload = _manifest_payload(enriched, now=current)
    digest = canonical_sha256(payload)
    path = directories["manifests"] / f"{digest}.json"
    _exclusive(path, payload)
    return path, payload, digest


def prepare_manifest(candidate: dict[str, Any], *, home: Path | None = None, now: str | datetime | None = None) -> dict[str, Any]:
    """Write the canonical private manifest and return only opaque metadata."""
    wanted = candidate.get("creation_receipt") or candidate.get("receipt_sha256")
    matched = next(
        ((receipt, journal) for receipt, journal in _valid_records(home) if receipt.get("receipt_sha256") == wanted),
        None,
    )
    if matched is None:
        raise CleanError("not Shadow-created")
    created, issuance = matched
    candidate_target = candidate.get("worktree") or candidate.get("target")
    if not isinstance(candidate_target, dict) or not isinstance(candidate_target.get("path"), str):
        raise CleanError("manifest lineage changed")
    if "worktree" in candidate and "target" in candidate and candidate["worktree"] != candidate["target"]:
        raise CleanError("manifest lineage changed")
    if "landed_ref" in candidate and candidate_target.get("landed_ref") not in {None, candidate["landed_ref"]}:
        raise CleanError("manifest lineage changed")
    try:
        candidate_path = _real_absolute(Path(candidate_target["path"]), "worktree")
    except CleanError:
        raise CleanError("manifest lineage changed") from None
    if candidate_path != Path(created["worktree"]["path"]).resolve():
        raise CleanError("manifest lineage changed")
    if candidate.get("entity") != created["claim"]["entity"] or candidate.get("checkpoint") != created["claim"]["checkpoint"]:
        raise CleanError("manifest lineage changed")
    if (candidate_target.get("landed_ref") or candidate.get("landed_ref")) != created["landed_ref"]:
        raise CleanError("manifest lineage changed")
    if candidate.get("creation_receipt") not in {None, created["receipt_sha256"]}:
        raise CleanError("manifest lineage changed")
    if candidate.get("receipt_sha256") not in {None, created["receipt_sha256"]}:
        raise CleanError("manifest lineage changed")
    if candidate.get("issuance_journal") not in {None, _journal_digest(issuance)}:
        raise CleanError("manifest lineage changed")
    if candidate.get("issuance_journal_sha256") not in {None, _journal_digest(issuance)}:
        raise CleanError("manifest lineage changed")
    refusal = _preview_refusal(matched[0], matched[1], (home or Path.home()).resolve())
    if refusal is not None:
        raise CleanError(refusal)
    _path, payload, digest = _prepare_manifest_record(candidate, home=home, now=now)
    receipt = candidate.get("creation_receipt") or candidate.get("receipt_sha256")
    if not isinstance(receipt, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt):
        raise CleanError("manifest creation receipt digest is invalid")
    return {
        "schema": CLEAN_MANIFEST_SCHEMA,
        "state": "prepared",
        "id": f"manifest@{digest[:12]}",
        "worktree_id": f"worktree@{receipt[:12]}",
        "expires_at": payload["expires_at"],
        "cas": digest,
    }


def validate_manifest(manifest: dict[str, Any], *, expected_sha256: str | None = None, now: str | datetime | None = None) -> str:
    if not isinstance(manifest, dict) or manifest.get("schema") != CLEAN_MANIFEST_SCHEMA:
        raise CleanError("clean manifest schema is not supported")
    expected_keys = {"schema", "generated_at", "expires_at", "target", "entity", "checkpoint", "creation_receipt", "issuance_journal", "lifecycle_target"}
    if set(manifest) != expected_keys:
        raise CleanError("clean manifest has unexpected fields")
    expires = _utc(manifest["expires_at"])
    current = _utc(now) if now is not None else datetime.now(timezone.utc)
    if expires <= current:
        raise CleanError("manifest expired")
    target = manifest.get("target")
    lifecycle = manifest.get("lifecycle_target")
    if not isinstance(target, dict) or not isinstance(lifecycle, dict):
        raise CleanError("clean manifest target is malformed")
    if lifecycle != {
        "kind": target.get("kind"),
        "head": target.get("head"),
        "landed_ref": target.get("landed_ref"),
    }:
        raise CleanError("clean manifest target binding changed")
    if target.get("kind") != "worktree" or not isinstance(target.get("path"), str):
        raise CleanError("clean manifest target is malformed")
    digest = canonical_sha256(manifest)
    if expected_sha256 is not None and digest != expected_sha256:
        raise CleanError("manifest changed since preview")
    return digest


def _status_snapshot(target: Path) -> tuple[str, str]:
    """Return the complete Git cleanliness proof for one target."""
    status = _git(
        target, "status", "--porcelain=v1", "--ignored=matching",
        "--untracked-files=all",
    ).stdout
    if status:
        lines = status.splitlines()
        if any(line.startswith("!!") for line in lines):
            raise CleanError("ignored files exist")
        if any(line.startswith("??") for line in lines):
            raise CleanError("untracked files exist")
        raise CleanError("worktree is dirty")
    submodules = _git(target, "submodule", "status", "--recursive").stdout.strip()
    if submodules:
        raise CleanError("submodule state exists")
    return status, hashlib.sha256(status.encode("utf-8")).hexdigest()


def _tree_snapshot(target: Path) -> str:
    """Return the immutable tracked content identity for a clean worktree."""
    tree = _git(target, "rev-parse", "HEAD^{tree}").stdout.strip()
    if not OID_RE.fullmatch(tree):
        raise CleanError("worktree content identity is unavailable")
    return tree


def _worktree_listing(source: Path) -> tuple[str, set[Path]]:
    listing = _git(source, "worktree", "list", "--porcelain").stdout
    paths = {
        Path(line.removeprefix("worktree ")).resolve()
        for line in listing.splitlines()
        if line.startswith("worktree ")
    }
    return listing, paths


def _listing_without_lock_digest(listing: str) -> str:
    """Normalize Git's lock annotation while preserving registration/CAS."""
    normalized = "\n".join(line for line in listing.splitlines() if not line.startswith("locked "))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _process_holds(path: Path) -> None:
    """Refuse unless the host can prove no process owns the target.

    Linux exposes the required boundary in /proc. macOS has no equivalent
    portable filesystem API, so use its bounded lsof interface and fail
    closed when that interface is unavailable or cannot complete.
    """
    target = path.resolve()
    proc = Path("/proc")
    if proc.is_dir():
        try:
            entries = sorted((entry for entry in proc.iterdir() if entry.name.isdigit()), key=lambda item: int(item.name))
        except OSError as exc:
            raise CleanError("process inspection unavailable") from exc
        if len(entries) > 4096:
            raise CleanError("process inspection unavailable")
        for entry in entries:
            try:
                cwd = Path(os.readlink(entry / "cwd"))
                if cwd == target or target in cwd.parents:
                    raise CleanError("process holds worktree")
                for fd in (entry / "fd").iterdir():
                    try:
                        opened = Path(os.readlink(fd))
                    except FileNotFoundError:
                        # The descriptor closed after enumeration. Other
                        # read errors leave a live holder uninspected.
                        continue
                    if opened == target or target in opened.parents:
                        raise CleanError("process holds worktree")
            except CleanError:
                raise
            except OSError as exc:
                # Only a demonstrably exited process is harmless. exists()
                # can collapse permission/I/O errors into false on some
                # Python versions, which is not proof of absence.
                try:
                    entry.stat()
                except FileNotFoundError:
                    continue
                except OSError as stat_exc:
                    raise CleanError("process inspection unavailable") from stat_exc
                raise CleanError("process inspection unavailable") from exc
        return
    lsof = shutil.which("lsof")
    if not lsof:
        raise CleanError("process inspection unavailable")
    try:
        result = subprocess.run(
            [lsof, "-n", "-F", "p", "+D", str(target), "-x", "f"],
            capture_output=True, text=True, check=False, timeout=15,
            env=_shadow_git.sanitized_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CleanError("process inspection unavailable") from exc
    if result.returncode not in (0, 1) or result.stderr.strip():
        raise CleanError("process inspection unavailable")
    pids = {
        line[1:]
        for line in result.stdout.splitlines()
        if line.startswith("p") and line[1:].isdigit()
    }
    if len(pids) > 4096:
        raise CleanError("process inspection unavailable")
    if pids:
        raise CleanError("process holds worktree")
    # lsof emits file fields even when only PID fields are requested. A PID
    # already proves a holder; absence requires a clean no-match completion,
    # never unrecognized or partial nonempty output.
    if result.stdout:
        raise CleanError("process inspection unavailable")


def _terminal_checkpoint(home: Path, entity: str, checkpoint: str) -> tuple[Path, str]:
    try:
        payload = _board.snapshot(home=home)
    except _board.BoardError as exc:
        raise CleanError(str(exc)) from None
    if not payload:
        raise CleanError("canonical board is unavailable")
    entity_record = next((item for item in payload["entities"] if item["id"] == entity), None)
    if entity_record is None:
        raise CleanError("entity is not registered on this computer")
    plan = Path(entity_record["plan"])
    if plan.is_symlink() or not plan.is_file():
        raise CleanError("entity plan is unavailable")
    try:
        text = _board.read_plan_text(plan)
    except (_board.BoardError, OSError, UnicodeError) as exc:
        raise CleanError("entity plan is unavailable") from exc
    rows = [
        match for line in text.splitlines()
        for match in [_board._grammar.ROW_RE.fullmatch(line)]
        if match is not None and match.group("id") == checkpoint
    ]
    if len(rows) != 1 or rows[0].group("state") not in {"completed", "blocked"}:
        raise CleanError("checkpoint is not terminal")
    if any(item["entity"] == entity and item["row"] == checkpoint for item in payload["claims"]):
        raise CleanError("active claim")
    return plan, rows[0].group("state")


def _receipt_for_manifest(manifest: dict[str, Any], home: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    wanted = manifest["creation_receipt"]
    for receipt, journal in _valid_records(home):
        if receipt.get("receipt_sha256") == wanted and journal.get("receipt_sha256") == wanted:
            if _journal_digest(journal) != manifest["issuance_journal"]:
                raise CleanError("issuance journal changed since preview")
            return receipt, journal
    raise CleanError("not Shadow-created")


def _target_snapshot(manifest: dict[str, Any], receipt: dict[str, Any], journal: dict[str, Any], home: Path) -> dict[str, Any]:
    target_spec = manifest["target"]
    target = Path(target_spec["path"])
    if _real_absolute(target, "worktree") != target or target.is_symlink() or not target.is_dir():
        raise CleanError("symlink or missing worktree")
    metadata = target.lstat()
    if metadata.st_dev != receipt["worktree"]["device"] or metadata.st_ino != receipt["worktree"]["inode"]:
        raise CleanError("worktree changed since preview")
    if "device" in target_spec and (target_spec["device"], target_spec["inode"]) != (metadata.st_dev, metadata.st_ino):
        raise CleanError("changed since preview")
    head = _git(target, "rev-parse", "HEAD").stdout.strip()
    if head != target_spec["head"]:
        raise CleanError("worktree HEAD changed since preview")
    _status, status_sha = _status_snapshot(target)
    tree_sha = _tree_snapshot(target)
    source = Path(journal["source_repo"])
    if _source_identity(source) != receipt["source"]["repository"]:
        raise CleanError("source repository identity changed")
    listing, paths = _worktree_listing(source)
    if target.resolve() not in paths:
        raise CleanError("worktree is not a registered linked worktree")
    expected_snapshot = {
        "device": metadata.st_dev, "inode": metadata.st_ino, "mode": metadata.st_mode,
        "mtime_ns": metadata.st_mtime_ns, "ctime_ns": metadata.st_ctime_ns,
        "status_sha256": status_sha,
        "worktree_listing_sha256": hashlib.sha256(listing.encode("utf-8")).hexdigest(),
        "tree_sha256": tree_sha,
    }
    for key, actual in expected_snapshot.items():
        if key == "worktree_listing_sha256" and target_spec.get(key) != actual:
            if target_spec.get("worktree_listing_unlocked_sha256") != _listing_without_lock_digest(listing):
                raise CleanError("manifest lacks the exact unchanged target snapshot")
            continue
        if key not in target_spec or target_spec[key] != actual:
            raise CleanError("manifest lacks the exact unchanged target snapshot")
    common = Path(_git(target, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()).resolve()
    admin = Path(_git(target, "rev-parse", "--path-format=absolute", "--git-dir").stdout.strip()).resolve()
    if common != Path(receipt["git"]["common_dir"]).resolve() or admin != Path(receipt["git"]["admin_dir"]).resolve():
        raise CleanError("worktree Git registration changed")
    source_common = Path(_git(source, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()).resolve()
    if common != source_common:
        raise CleanError("worktree does not share the source Git store")
    if admin == common:
        raise CleanError("primary worktree")
    resolved_ref = _git(source, "rev-parse", "--verify", target_spec["landed_ref"]).stdout.strip()
    ancestor = subprocess.run(
        ["git", "-C", str(source), "merge-base", "--is-ancestor", head, resolved_ref],
        capture_output=True, text=True, check=False, env=_shadow_git.sanitized_git_env(),
    )
    if ancestor.returncode:
        raise CleanError("work is not landed")
    _process_holds(target)
    return {
        "target": target,
        "source": source,
        "metadata": metadata,
        "head": head,
        "status_sha256": status_sha,
        "listing_sha256": hashlib.sha256(listing.encode("utf-8")).hexdigest(),
        "listing_without_lock_sha256": _listing_without_lock_digest(listing),
        "tree_sha256": tree_sha,
        "common_dir": common,
        "admin_dir": admin,
    }


def _load_manifest(path: Path, *, home: Path | None = None) -> tuple[dict[str, Any], str]:
    canonical = _real_absolute(path, "manifest")
    directories = _clean_dirs(home, create=False)
    if not canonical.is_relative_to(directories["manifests"]):
        raise CleanError("manifest must be the canonical private Shadow manifest")
    try:
        value = json.loads(_read(canonical))
    except (json.JSONDecodeError, CleanError) as exc:
        raise CleanError("manifest is malformed") from exc
    digest = validate_manifest(value)
    if canonical.name != f"{digest}.json":
        raise CleanError("manifest changed since preview")
    return value, digest


def resolve_manifest(manifest_id: str, *, home: Path | None = None) -> tuple[dict[str, Any], str, Path]:
    """Resolve an opaque prepare identity inside Shadow's private manifest root."""
    match = MANIFEST_ID_RE.fullmatch(manifest_id)
    if match is None:
        raise CleanError("manifest identity is invalid")
    directories = _clean_dirs(home, create=False)
    matches: list[tuple[dict[str, Any], str, Path]] = []
    for path in sorted(directories["manifests"].glob("*.json")):
        try:
            manifest, digest = _load_manifest(path, home=home)
        except (CleanError, OSError, json.JSONDecodeError):
            # Resolution by opaque id must still find an authenticated,
            # expired manifest when an in-flight retirement journal exists;
            # apply_manifest will permit only that journal-bound recovery.
            try:
                manifest = json.loads(_read(path))
                digest = canonical_sha256(manifest)
                if path.name != f"{digest}.json":
                    continue
                validate_manifest(manifest, expected_sha256=digest, now="1970-01-01T00:00:00Z")
            except (CleanError, OSError, json.JSONDecodeError, TypeError):
                continue
        if digest.startswith(match.group(1)):
            matches.append((manifest, digest, path))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise CleanError("manifest identity is ambiguous")
    raise CleanError("manifest identity is unknown or expired")


def _manifest_path(value: Path | str, *, home: Path) -> Path:
    if isinstance(value, str) and MANIFEST_ID_RE.fullmatch(value):
        return resolve_manifest(value, home=home)[2]
    return _real_absolute(Path(value), "manifest")


def _trash_directory(trash_root: Path | None) -> Path:
    target = _real_absolute(
        trash_root if trash_root is not None else Path.home() / ".Trash", "Trash root"
    )
    if target.is_symlink() or not target.is_dir():
        raise CleanError("Trash root is unavailable")
    return target


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise CleanError("filesystem directory could not be synchronized") from exc


def _atomic_move_noreplace(
    source: Path, destination: Path, *, expected_source: tuple[int, int] | None = None,
) -> None:
    """Rename one directory without ever replacing an intervening entry."""
    flags = (getattr(os, "O_RDONLY", 0) | getattr(os, "O_DIRECTORY", 0)
             | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0))
    oldfd = newfd = -1
    try:
        oldfd = os.open(source.parent, flags)
        newfd = os.open(destination.parent, flags)
        old_stat, new_stat = os.fstat(oldfd), os.fstat(newfd)
        if not stat.S_ISDIR(old_stat.st_mode) or not stat.S_ISDIR(new_stat.st_mode) or old_stat.st_dev != new_stat.st_dev:
            raise CleanError("atomic no-replace move requires one filesystem")
        source_stat = os.stat(source.name, dir_fd=oldfd, follow_symlinks=False)
        if not stat.S_ISDIR(source_stat.st_mode) or (expected_source is not None and (source_stat.st_dev, source_stat.st_ino) != expected_source):
            raise CleanError("source changed before atomic move")
        libc = ctypes.CDLL(None, use_errno=True)
        encoded_old = os.fsencode(source.name)
        encoded_new = os.fsencode(destination.name)
        if sys.platform == "darwin":
            if not hasattr(libc, "renameatx_np"):
                raise CleanError("atomic no-replace move is unavailable")
            libc.renameatx_np.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            libc.renameatx_np.restype = ctypes.c_int
            result = libc.renameatx_np(oldfd, encoded_old, newfd, encoded_new, 0x00000004)
        elif sys.platform == "linux":
            # renameat2 is syscall 316 on x86_64 and 276 on arm64/aarch64.
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is not None:
                renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
                renameat2.restype = ctypes.c_int
                result = renameat2(oldfd, encoded_old, newfd, encoded_new, 0x1)
            else:
                raise CleanError("atomic no-replace move is unavailable")
        else:
            raise CleanError("atomic no-replace move is unavailable")
        if result != 0:
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                raise CleanError("destination appeared during atomic move")
            if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
                raise CleanError("atomic no-replace move is unavailable")
            raise CleanError("atomic worktree move failed")
        try:
            os.fsync(oldfd)
            if newfd != oldfd:
                os.fsync(newfd)
        except OSError as exc:
            raise CleanMoveCommittedError("worktree move committed; filesystem sync is incomplete") from exc
    except OSError as exc:
        raise CleanError("atomic no-replace move is unavailable") from exc
    finally:
        if oldfd >= 0:
            os.close(oldfd)
        if newfd >= 0:
            os.close(newfd)


def _private_stage_path(parent: Path, worktree_id: str, digest: str) -> Path:
    return parent / f".shadow-clean-{worktree_id[len('worktree@'):]}-{digest[:12]}" / "payload"


def _create_private_stage(parent: Path, worktree_id: str, digest: str) -> Path:
    """Create an exclusive mode-0700 transaction directory and payload path."""
    stage_dir = _private_stage_path(parent, worktree_id, digest).parent
    try:
        stage_dir.mkdir(mode=0o700)
        os.chmod(stage_dir, 0o700)
        metadata = stage_dir.lstat()
    except FileExistsError as exc:
        raise CleanError("private cleanup transaction already exists") from exc
    except OSError as exc:
        raise CleanError("private cleanup transaction could not be created") from exc
    if stage_dir.is_symlink() or not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise CleanError("private cleanup transaction is unsafe")
    return stage_dir / "payload"


def _remove_empty_private_stage(payload: Path) -> None:
    """Retire only an empty private transaction directory."""
    stage_dir = payload.parent
    try:
        if payload.exists() or payload.is_symlink():
            return
        if stage_dir.is_symlink() or not stage_dir.is_dir():
            return
        stage_dir.rmdir()
    except OSError:
        # An orphaned empty stage is harmless and remains recoverable; never
        # recursively remove a transaction directory.
        return


def _validate_private_stage_path(payload: Path, parent: Path, worktree_id: str, digest: str) -> None:
    """Require the journaled payload to be the deterministic private stage."""
    if payload != _private_stage_path(parent, worktree_id, digest):
        raise CleanError("private cleanup transaction lineage changed")
    stage_dir = payload.parent
    try:
        metadata = stage_dir.lstat()
    except OSError as exc:
        raise CleanError("private cleanup transaction is unavailable") from exc
    if stage_dir.is_symlink() or not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise CleanError("private cleanup transaction is unsafe")


def _read_git_lock(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise CleanError("worktree lock state is unsafe")
        data = os.read(descriptor, 4096)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise CleanError("worktree lock state is unavailable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise CleanError("worktree lock state changed while being read")
    return data.decode("utf-8", errors="strict").strip()


def _crash_point(stage: str, crash_at: str | None) -> None:
    if crash_at == stage:
        raise CleanError(f"simulated crash at {stage}; retry the same receipt")


def _lock_reason(worktree_id: str, manifest_digest: str) -> str:
    return f"shadow clean {worktree_id} {manifest_digest}"


def _worktree_lock(info: dict[str, Any], worktree_id: str, manifest_digest: str) -> None:
    admin: Path = info["admin_dir"]
    locked = admin / "locked"
    reason = _lock_reason(worktree_id, manifest_digest)
    if locked.is_symlink():
        raise CleanError("worktree lock state is unsafe")
    if locked.exists() or locked.is_symlink():
        reason = _read_git_lock(locked)
        if reason != _lock_reason(worktree_id, manifest_digest):
            raise CleanError("worktree is already locked")
        return
    _git(
        info["source"], "worktree", "lock", "--reason",
        reason, "--", str(info["target"]),
    )


def _rollback_apply_lock(info: dict[str, Any], worktree_id: str, manifest_digest: str, journal_path: Path) -> None:
    """Undo a pre-rename refusal while retaining a durable crash journal."""
    try:
        journal = json.loads(_read(journal_path))
    except (CleanError, OSError, json.JSONDecodeError):
        return
    # A moved journal owns the only recoverable Trash copy. Never unlock or
    # retire that transaction merely because a retry currently sees an
    # intervening original-path entry; leave it durable for a safe retry.
    if journal.get("state") != "prepared":
        return
    target = Path(journal.get("target", ""))
    try:
        target_stat = target.lstat()
    except (OSError, ValueError):
        return
    if (target_stat.st_dev, target_stat.st_ino) != (journal.get("device"), journal.get("inode")):
        # The canonical path no longer contains the authenticated worktree;
        # never unlock or retire a journal around an untrusted replacement.
        return
    locked = info["admin_dir"] / "locked"
    if locked.is_file() and not locked.is_symlink():
        try:
            reason = _read_git_lock(locked)
        except CleanError:
            return
        if reason == _lock_reason(worktree_id, manifest_digest):
            try:
                _git(info["source"], "worktree", "unlock", "--", str(info["target"]))
            except CleanError:
                return
            journal_path.unlink(missing_ok=True)
            _remove_empty_private_stage(Path(journal.get("private_stage", "")))


def _final_apply_check(info: dict[str, Any], *, worktree_id: str, manifest_digest: str, journal_path: Path) -> None:
    """Recheck every mutable predicate immediately before the rename."""
    try:
        latest_metadata = info["target"].lstat()
        latest_head = _git(info["target"], "rev-parse", "HEAD").stdout.strip()
        _status, latest_status_sha = _status_snapshot(info["target"])
        latest_tree_sha = _tree_snapshot(info["target"])
        latest_listing, _paths = _worktree_listing(info["source"])
        _process_holds(info["target"])
        expected_metadata = info.get("expected_metadata", {
            "st_dev": info["metadata"].st_dev, "st_ino": info["metadata"].st_ino,
            "st_mode": info["metadata"].st_mode, "st_mtime_ns": info["metadata"].st_mtime_ns,
            "st_ctime_ns": info["metadata"].st_ctime_ns,
        })
        for key in ("st_dev", "st_ino", "st_mode", "st_mtime_ns", "st_ctime_ns"):
            if getattr(latest_metadata, key) != expected_metadata[key]:
                raise CleanError("worktree changed after lock")
        if latest_head != info["head"] or latest_status_sha != info["status_sha256"] or latest_tree_sha != info["tree_sha256"]:
            raise CleanError("worktree changed after lock")
        if _listing_without_lock_digest(latest_listing) != info["listing_without_lock_sha256"]:
            raise CleanError("worktree registration changed after lock")
        current = info["target"].lstat()
        if (current.st_dev, current.st_ino) != (info["metadata"].st_dev, info["metadata"].st_ino):
            raise CleanError("worktree changed after lock")
    except CleanError as exc:
        if not str(exc).startswith("simulated crash"):
            _rollback_apply_lock(info, worktree_id, manifest_digest, journal_path)
        raise


def _post_move_check(info: dict[str, Any], destination: Path, *, worktree_id: str, manifest_digest: str) -> None:
    if info["target"].exists() or info["target"].is_symlink():
        raise CleanError("source race recreated the original worktree")
    metadata = destination.lstat()
    if (metadata.st_dev, metadata.st_ino) != (info["metadata"].st_dev, info["metadata"].st_ino):
        raise CleanError("Trash artifact changed after move")
    head = _git(destination, "rev-parse", "HEAD").stdout.strip()
    _status, status_sha = _status_snapshot(destination)
    tree_sha = _tree_snapshot(destination)
    if head != info["head"] or status_sha != info["status_sha256"] or tree_sha != info["tree_sha256"]:
        raise CleanError("Trash worktree content changed after move")
    _process_holds(destination)
    if not _registration_lock_state(info["source"], info["target"], worktree_id, manifest_digest):
        raise CleanError("Trash worktree is not locked by this retirement")


def _post_stage_check(info: dict[str, Any], stage: Path) -> os.stat_result:
    """Validate the first-hop payload before sending it to public Trash."""
    metadata = stage.lstat()
    if (metadata.st_dev, metadata.st_ino) != (info["metadata"].st_dev, info["metadata"].st_ino):
        raise CleanError("private cleanup payload changed")
    head = _git(stage, "rev-parse", "HEAD").stdout.strip()
    _status, status_sha = _status_snapshot(stage)
    tree_sha = _tree_snapshot(stage)
    if head != info["head"] or status_sha != info["status_sha256"] or tree_sha != info["tree_sha256"]:
        raise CleanError("private cleanup payload changed")
    _process_holds(stage)
    if info["target"].exists() or info["target"].is_symlink():
        raise CleanError("source race recreated the original worktree")
    return metadata


def _flag_trash_recovery(journal_path: Path, journal: dict[str, Any], reason: str) -> None:
    """Persist a recoverable source-race marker without issuing a receipt."""
    marked = {**journal, "source_race": True, "recovery_required": True}
    try:
        _replace(journal_path, marked)
    except CleanError:
        # The original operation is already refusing; leave its last durable
        # journal state in place rather than risking a partial replacement.
        pass


def _flag_restore_recovery(journal_path: Path, journal: dict[str, Any], *, state: str | None = None) -> None:
    """Persist restore source-race state without unlocking or receipt."""
    marked = {**journal, "source_race": True, "recovery_required": True}
    if state is not None:
        marked["state"] = state
    try:
        _replace(journal_path, marked)
    except CleanError:
        pass


def _receipt_path_for_id(worktree_id: str, home: Path) -> Path:
    directories = _clean_dirs(home, create=False)
    matches = []
    if directories["trash-receipts"].is_dir():
        for path in sorted(directories["trash-receipts"].glob("*.json")):
            try:
                value = json.loads(_read(path))
            except (CleanError, OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("worktree_id") == worktree_id:
                matches.append(path)
    if len(matches) != 1:
        raise CleanError("Trash receipt is unknown or ambiguous")
    return matches[0]


def _load_trash_receipt(worktree_id: str, home: Path) -> tuple[dict[str, Any], Path]:
    if WORKTREE_ID_RE.fullmatch(worktree_id) is None:
        raise CleanError("worktree receipt identity is invalid")
    path = _receipt_path_for_id(worktree_id, home)
    try:
        value = json.loads(_read(path))
    except (CleanError, OSError, json.JSONDecodeError) as exc:
        raise CleanError("Trash receipt is malformed") from exc
    required = {"schema", "state", "worktree_id", "manifest_sha256", "creation_receipt", "issuance_journal", "target", "trash", "device", "inode", "cas", "source_repo", "plan", "entity", "checkpoint", "head", "tree_sha256", "status_sha256", "receipt_sha256"}
    if not isinstance(value, dict) or set(value) - (required | {"restored_at"}) or not required.issubset(value):
        raise CleanError("Trash receipt is malformed")
    if value["schema"] != TRASH_RECEIPT_SCHEMA or value["worktree_id"] != worktree_id:
        raise CleanError("Trash receipt is malformed")
    if value["receipt_sha256"] != canonical_sha256({key: item for key, item in value.items() if key != "receipt_sha256"}):
        raise CleanError("Trash receipt digest changed")
    authenticated = [
        (created, journal) for created, journal in _valid_records(home)
        if created.get("receipt_sha256") == value.get("creation_receipt")
    ]
    if len(authenticated) != 1:
        raise CleanError("Trash receipt is not backed by an issued Shadow receipt")
    created, journal = authenticated[0]
    if (
        worktree_id != f"worktree@{created['receipt_sha256'][:12]}"
        or value["issuance_journal"] != _journal_digest(journal)
        or value["entity"] != created["claim"]["entity"]
        or value["checkpoint"] != created["claim"]["checkpoint"]
        or value["source_repo"] != journal["source_repo"]
        or value["target"] != created["worktree"]["path"]
        or value["device"] != created["worktree"]["device"]
        or value["inode"] != created["worktree"]["inode"]
    ):
        raise CleanError("Trash receipt lineage changed")
    return value, path


def _load_trash_journal(path: Path, *, digest: str, worktree_id: str) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except (CleanError, OSError, json.JSONDecodeError) as exc:
        raise CleanError("Trash journal is malformed") from exc
    required = {"schema", "state", "manifest_sha256", "worktree_id", "target", "trash", "private_stage", "source_race", "recovery_required", "device", "inode", "mode", "mtime_ns", "ctime_ns", "cas", "source_repo", "plan", "head", "tree_sha256", "status_sha256", "listing_without_lock_sha256", "creation_receipt", "issuance_journal", "common_dir", "admin_dir", "lock_reason"}
    if not isinstance(value, dict) or set(value) != required:
        raise CleanError("Trash journal is malformed")
    if value["schema"] != TRASH_JOURNAL_SCHEMA or value["manifest_sha256"] != digest or value["worktree_id"] != worktree_id:
        raise CleanError("Trash journal does not match this manifest")
    if Path(value["private_stage"]) != _private_stage_path(Path(value["target"]).parent, worktree_id, digest):
        raise CleanError("Trash journal private stage lineage changed")
    if not isinstance(value["source_race"], bool) or not isinstance(value["recovery_required"], bool):
        raise CleanError("Trash journal recovery state is malformed")
    if value["lock_reason"] != _lock_reason(worktree_id, digest) or worktree_id != f"worktree@{value['creation_receipt'][:12]}":
        raise CleanError("Trash journal lock binding changed")
    if value["state"] not in {"prepared", "moved"}:
        raise CleanError("Trash journal state is unsupported")
    return value


def apply_manifest(
    manifest: Path | str,
    *,
    expected_sha256: str,
    by: str | None = None,
    home: Path | None = None,
    trash_root: Path | None = None,
    now: str | datetime | None = None,
    crash_at: str | None = None,
) -> dict[str, Any]:
    """Move one fresh, exact managed worktree into recoverable Trash."""
    private_home = (home or Path.home()).resolve()
    path = _manifest_path(manifest, home=private_home)
    manifest_expired = False
    try:
        value, digest = _load_manifest(path, home=private_home)
    except CleanError as exc:
        # An expired manifest can only resume an already durable in-flight
        # journal. It can never start a new move.
        if "expired" not in str(exc):
            raise
        manifest_expired = True
        try:
            value = json.loads(_read(path))
            digest = validate_manifest(value, expected_sha256=expected_sha256, now="1970-01-01T00:00:00Z")
            journal_probe = _clean_dirs(private_home, create=False)["trash-journals"] / f"{digest}.json"
            if not journal_probe.is_file():
                raise CleanError("manifest expired")
            _load_trash_journal(journal_probe, digest=digest, worktree_id=f"worktree@{value['creation_receipt'][:12]}")
        except (CleanError, OSError, json.JSONDecodeError, KeyError):
            raise exc
    if digest != expected_sha256:
        raise CleanError("manifest changed since preview")
    receipt, issuance = _receipt_for_manifest(value, private_home)
    worktree_id = f"worktree@{receipt['receipt_sha256'][:12]}"
    trash = _trash_directory(trash_root)
    target = Path(value["target"]["path"])
    if by is not None:
        try:
            _board.validate_owner(by)
        except _board.BoardError as exc:
            raise CleanError(str(exc)) from None
    plan, _state = _terminal_checkpoint(private_home, value["entity"], value["checkpoint"])
    journal_dirs = _clean_dirs(private_home, create=True)
    journal_path = journal_dirs["trash-journals"] / f"{digest}.json"
    receipt_path = journal_dirs["trash-receipts"] / f"{receipt['receipt_sha256']}.json"
    if not journal_path.exists():
        locked = Path(receipt["git"]["admin_dir"]) / "locked"
        if locked.is_symlink():
            raise CleanError("worktree lock state is unsafe")
        if locked.exists():
            raise CleanError("worktree is already locked")
    if receipt_path.exists() or receipt_path.is_symlink():
        existing, _ = _load_trash_receipt(worktree_id, private_home)
        artifact = Path(existing["trash"])
        original = Path(existing["target"])
        if existing.get("state") == "trashed" and artifact.is_dir() and not artifact.is_symlink() and not original.exists():
            metadata = artifact.lstat()
            if (metadata.st_dev, metadata.st_ino) != (existing["device"], existing["inode"]):
                raise CleanError("Trash artifact changed after retirement")
            admin = Path(receipt["git"]["admin_dir"]) / "locked"
            if admin.is_symlink() or not admin.is_file() or _read_git_lock(admin) != _lock_reason(worktree_id, digest):
                raise CleanError("Trash worktree lock state changed")
            if journal_path.exists() or journal_path.is_symlink():
                pending = _load_trash_journal(journal_path, digest=digest, worktree_id=worktree_id)
                if pending["state"] != "moved" or pending["trash"] != str(artifact):
                    raise CleanError("Trash journal is inconsistent")
                journal_path.unlink()
                _fsync_directory(journal_path.parent)
            return {"schema": "shadow.clean-apply.v1", "action": "already_trashed", "changed": False, "receipt": worktree_id}
        raise CleanError("Trash receipt already exists and is inconsistent")
    with _board.project_lock(plan):
        _crash_point("before_lock", crash_at)
        existing_journal = None
        if journal_path.exists() or journal_path.is_symlink():
            existing_journal = _load_trash_journal(journal_path, digest=digest, worktree_id=worktree_id)
        if existing_journal is not None and existing_journal["state"] == "moved":
            destination = Path(existing_journal["trash"])
            private_stage = Path(existing_journal["private_stage"])
            if not destination.is_dir() or destination.is_symlink():
                raise CleanError("Trash artifact is missing or unsafe")
            moved_stat = destination.lstat()
            if (moved_stat.st_dev, moved_stat.st_ino) != (receipt["worktree"]["device"], receipt["worktree"]["inode"]):
                raise CleanError("Trash artifact changed after retirement")
            info = {
                "target": Path(existing_journal["target"]), "source": Path(existing_journal["source_repo"]),
                "metadata": moved_stat, "head": existing_journal["head"],
                "status_sha256": existing_journal["status_sha256"], "listing_sha256": "",
                "listing_without_lock_sha256": existing_journal["listing_without_lock_sha256"],
                "tree_sha256": existing_journal["tree_sha256"], "common_dir": Path(receipt["git"]["common_dir"]),
                "admin_dir": Path(receipt["git"]["admin_dir"]),
                "expected_metadata": {
                    "st_dev": existing_journal["device"], "st_ino": existing_journal["inode"],
                    "st_mode": existing_journal["mode"], "st_mtime_ns": existing_journal["mtime_ns"],
                    "st_ctime_ns": existing_journal["ctime_ns"],
                },
            }
            _worktree_lock(info, worktree_id, digest)
        elif (
            existing_journal is not None
            and existing_journal["state"] == "prepared"
            and not Path(existing_journal["target"]).exists()
            and Path(existing_journal["private_stage"]).is_dir()
            and not Path(existing_journal["trash"]).exists()
        ):
            private_stage = Path(existing_journal["private_stage"])
            destination = Path(existing_journal["trash"])
            staged_stat = private_stage.lstat()
            if (staged_stat.st_dev, staged_stat.st_ino) != (receipt["worktree"]["device"], receipt["worktree"]["inode"]):
                raise CleanError("private cleanup payload changed")
            info = {
                "target": Path(existing_journal["target"]), "source": Path(existing_journal["source_repo"]),
                "metadata": staged_stat, "head": existing_journal["head"],
                "status_sha256": existing_journal["status_sha256"], "listing_sha256": "",
                "listing_without_lock_sha256": existing_journal["listing_without_lock_sha256"],
                "tree_sha256": existing_journal["tree_sha256"], "common_dir": Path(receipt["git"]["common_dir"]),
                "admin_dir": Path(receipt["git"]["admin_dir"]),
            }
            _worktree_lock(info, worktree_id, digest)
        elif (
            existing_journal is not None
            and existing_journal["state"] == "prepared"
            and not Path(existing_journal["target"]).exists()
            and Path(existing_journal["trash"]).is_dir()
        ):
            destination = Path(existing_journal["trash"])
            private_stage = Path(existing_journal["private_stage"])
            moved_stat = destination.lstat()
            if (moved_stat.st_dev, moved_stat.st_ino) != (receipt["worktree"]["device"], receipt["worktree"]["inode"]):
                raise CleanError("Trash artifact changed after retirement")
            info = {
                "target": Path(existing_journal["target"]), "source": Path(existing_journal["source_repo"]),
                "metadata": moved_stat, "head": existing_journal["head"],
                "status_sha256": existing_journal["status_sha256"], "listing_sha256": "",
                "listing_without_lock_sha256": existing_journal["listing_without_lock_sha256"],
                "tree_sha256": existing_journal["tree_sha256"], "common_dir": Path(receipt["git"]["common_dir"]),
                "admin_dir": Path(receipt["git"]["admin_dir"]),
            }
            _worktree_lock(info, worktree_id, digest)
        elif existing_journal is not None and existing_journal["state"] == "prepared":
            # Retry an intent whose target is still present from the journal
            # snapshot. This lets the final evaluator safely detect a dirty,
            # changed, or otherwise refused target and remove its exact lock
            # without re-authenticating a mutable candidate as new work.
            target_path = Path(existing_journal["target"])
            if target_path.is_symlink() or not target_path.is_dir():
                raise CleanError("worktree changed since preview")
            current = target_path.lstat()
            info = {
                "target": target_path, "source": Path(existing_journal["source_repo"]),
                "metadata": current, "head": existing_journal["head"],
                "status_sha256": existing_journal["status_sha256"], "listing_sha256": "",
                "listing_without_lock_sha256": existing_journal["listing_without_lock_sha256"],
                "tree_sha256": existing_journal["tree_sha256"], "common_dir": Path(existing_journal["common_dir"]),
                "admin_dir": Path(existing_journal["admin_dir"]),
                "expected_metadata": {
                    "st_dev": existing_journal["device"], "st_ino": existing_journal["inode"],
                    "st_mode": existing_journal["mode"], "st_mtime_ns": existing_journal["mtime_ns"],
                    "st_ctime_ns": existing_journal["ctime_ns"],
                },
            }
            private_stage = Path(existing_journal["private_stage"])
            _worktree_lock(info, worktree_id, digest)
        else:
            info = _target_snapshot(value, receipt, issuance, private_home)
        # The source checkout and plan can change while the manifest was
        # waiting; re-read both predicates under the project lock.
        _terminal_checkpoint(private_home, value["entity"], value["checkpoint"])
        if info["metadata"].st_dev != trash.stat().st_dev:
            raise CleanError("Trash must be on the same device")
        if existing_journal is None:
            destination = trash / f".shadow-{receipt['receipt_sha256'][:12]}-{digest[:12]}"
            if destination.exists() or destination.is_symlink():
                raise CleanError("Trash destination already exists")
        destination = Path(existing_journal["trash"]) if existing_journal is not None else destination
        recovered_move = (
            existing_journal is not None and existing_journal["state"] == "prepared"
            and not Path(existing_journal["target"]).exists() and destination.is_dir()
        )
        if (existing_journal is None or existing_journal["state"] == "prepared") and not recovered_move and (destination.exists() or destination.is_symlink()):
            raise CleanError("Trash destination already exists")
        if existing_journal is None:
            private_stage = _create_private_stage(info["target"].parent, worktree_id, digest)
        elif existing_journal["state"] == "prepared":
            if private_stage.parent.exists():
                _validate_private_stage_path(private_stage, info["target"].parent, worktree_id, digest)
            elif not (destination.is_dir() and not info["target"].exists()):
                raise CleanError("private cleanup transaction is unavailable")
        elif private_stage.parent.exists():
            _validate_private_stage_path(private_stage, info["target"].parent, worktree_id, digest)
        journal = {
            "schema": TRASH_JOURNAL_SCHEMA,
            "state": "prepared",
            "manifest_sha256": digest,
            "worktree_id": worktree_id,
            "target": str(info["target"]),
            "trash": str(destination),
            "private_stage": str(private_stage),
            "source_race": False,
            "recovery_required": False,
            "device": info["metadata"].st_dev,
            "inode": info["metadata"].st_ino,
            "mode": info["metadata"].st_mode,
            "mtime_ns": info["metadata"].st_mtime_ns,
            "ctime_ns": info["metadata"].st_ctime_ns,
            "cas": digest,
            "source_repo": str(info["source"]),
            "plan": str(plan),
            "head": info["head"],
            "tree_sha256": info["tree_sha256"],
            "status_sha256": info["status_sha256"],
            "listing_without_lock_sha256": info["listing_without_lock_sha256"],
            "creation_receipt": receipt["receipt_sha256"],
            "issuance_journal": _journal_digest(issuance),
            "common_dir": str(info["common_dir"]),
            "admin_dir": str(info["admin_dir"]),
            "lock_reason": _lock_reason(worktree_id, digest),
        }
        if existing_journal is not None:
            journal = {**existing_journal, "private_stage": str(private_stage)}
        if existing_journal is None:
            _exclusive(journal_path, journal)
            _crash_point("after_journal", crash_at)
            _worktree_lock(info, worktree_id, digest)
        elif existing_journal["state"] == "prepared":
            _worktree_lock(info, worktree_id, digest)
        _crash_point("after_lock", crash_at)
        if manifest_expired and existing_journal is not None and existing_journal["state"] == "prepared":
            # An expired intent may recover only its exact owned lock; it may
            # never begin a new retirement after the short manifest TTL.
            if Path(existing_journal["target"]).exists():
                _rollback_apply_lock(info, worktree_id, digest, journal_path)
                raise CleanError("manifest expired")
            # A crash after the exact rename but before the journal's moved
            # transition leaves the target absent and the authenticated Trash
            # inode present.  Finalize that already-performed mutation even
            # after the short manifest TTL; do not perform a fresh move.
            if destination.is_dir() and not destination.is_symlink():
                moved_stat = destination.lstat()
                if (moved_stat.st_dev, moved_stat.st_ino) != (info["metadata"].st_dev, info["metadata"].st_ino):
                    raise CleanError("Trash artifact changed after retirement")
                # Leave the durable state at prepared until the common
                # recovered-move post-check below has passed.
            else:
                raise CleanError("manifest expired")
        if info["target"].exists():
            _final_apply_check(info, worktree_id=worktree_id, manifest_digest=digest, journal_path=journal_path)
            if not private_stage.exists():
                try:
                    _atomic_move_noreplace(
                        info["target"], private_stage,
                        expected_source=(info["metadata"].st_dev, info["metadata"].st_ino),
                    )
                except CleanError as exc:
                    _flag_trash_recovery(journal_path, journal, str(exc))
                    raise
                _crash_point("after_private_stage", crash_at)
            try:
                staged = _post_stage_check(info, private_stage)
                _atomic_move_noreplace(
                    private_stage, destination,
                    expected_source=(staged.st_dev, staged.st_ino),
                )
            except (CleanError, CleanMoveCommittedError) as exc:
                _flag_trash_recovery(journal_path, journal, str(exc))
                raise
            _fsync_directory(info["target"].parent)
            _fsync_directory(trash)
            try:
                _post_move_check(info, destination, worktree_id=worktree_id, manifest_digest=digest)
            except CleanError as exc:
                # Apply mismatches retain the locked Trash artifact and the
                # authenticated journal. Never unlock a potentially raced
                # source or issue a success receipt.
                _flag_trash_recovery(journal_path, journal, str(exc))
                raise
            _remove_empty_private_stage(private_stage)
            _crash_point("after_rename_before_journal", crash_at)
        elif private_stage.is_dir() and not destination.exists():
            # The first hop committed before a crash or collision. Validate
            # the private payload, then perform only the remaining hop.
            try:
                staged = _post_stage_check(info, private_stage)
                _atomic_move_noreplace(
                    private_stage, destination,
                    expected_source=(staged.st_dev, staged.st_ino),
                )
                _fsync_directory(info["target"].parent)
                _fsync_directory(trash)
                _post_move_check(info, destination, worktree_id=worktree_id, manifest_digest=digest)
            except (CleanError, CleanMoveCommittedError) as exc:
                _flag_trash_recovery(journal_path, journal, str(exc))
                raise
            _remove_empty_private_stage(private_stage)
        elif not destination.exists():
            raise CleanError("worktree disappeared before Trash move")
        elif recovered_move:
            # The second hop committed before the journal transition. Re-run
            # the full post-move boundary before issuing a receipt.
            try:
                _post_move_check(info, destination, worktree_id=worktree_id, manifest_digest=digest)
            except CleanError as exc:
                _flag_trash_recovery(journal_path, journal, str(exc))
                raise
        moved = {**journal, "state": "moved", "source_race": False, "recovery_required": False}
        _replace(journal_path, moved)
        _crash_point("after_rename", crash_at)
        public_receipt = {
            "schema": TRASH_RECEIPT_SCHEMA,
            "state": "trashed",
            "worktree_id": worktree_id,
            "manifest_sha256": digest,
            "creation_receipt": receipt["receipt_sha256"],
            "issuance_journal": _journal_digest(issuance),
            "entity": value["entity"],
            "checkpoint": value["checkpoint"],
            "target": str(info["target"]),
            "trash": str(destination),
            "device": info["metadata"].st_dev,
            "inode": info["metadata"].st_ino,
            "cas": digest,
            "source_repo": str(info["source"]),
            "plan": str(plan),
            "head": info["head"],
            "tree_sha256": info["tree_sha256"],
            "status_sha256": info["status_sha256"],
        }
        public_receipt["receipt_sha256"] = canonical_sha256(public_receipt)
        _exclusive(receipt_path, public_receipt)
        _crash_point("after_public_receipt", crash_at)
        journal_path.unlink(missing_ok=True)
        _fsync_directory(journal_path.parent)
        return {"schema": "shadow.clean-apply.v1", "action": "trashed", "changed": True, "receipt": worktree_id}


def _restore_content(receipt: dict[str, Any], target: Path) -> dict[str, str]:
    """Revalidate the Git content that was retired, including cleanliness."""
    head = _git(target, "rev-parse", "HEAD").stdout.strip()
    _status, status_sha = _status_snapshot(target)
    tree_sha = _tree_snapshot(target)
    if head != receipt["head"] or tree_sha != receipt["tree_sha256"] or status_sha != receipt["status_sha256"]:
        raise CleanError("Trash worktree content changed after retirement")
    return {"head": head, "tree_sha256": tree_sha, "status_sha256": status_sha}


def _restore_cas(receipt: dict[str, Any], metadata: os.stat_result, content: dict[str, str]) -> str:
    return canonical_sha256({
        "schema": "shadow.clean-restore-cas.v1",
        "worktree_id": receipt["worktree_id"],
        "manifest_sha256": receipt["manifest_sha256"],
        "trash": receipt["trash"],
        "target": receipt["target"],
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": metadata.st_mode,
        "mtime_ns": metadata.st_mtime_ns,
        **content,
        "lock_reason": _lock_reason(receipt["worktree_id"], receipt["manifest_sha256"]),
    })


def _validate_restored_target(receipt: dict[str, Any], target: Path, expected: str) -> os.stat_result:
    """Authenticate the exact inode and clean Git content before unlock."""
    metadata = target.lstat()
    if (metadata.st_dev, metadata.st_ino) != (receipt["device"], receipt["inode"]):
        raise CleanError("restored worktree identity changed")
    content = _restore_content(receipt, target)
    if _restore_cas(receipt, metadata, content) != expected:
        raise CleanError("restored worktree changed before unlock")
    _process_holds(target)
    return metadata


def _validate_restore_stage(receipt: dict[str, Any], stage: Path, expected: str) -> os.stat_result:
    """Authenticate the private restore payload before its second hop."""
    metadata = stage.lstat()
    if (metadata.st_dev, metadata.st_ino) != (receipt["device"], receipt["inode"]):
        raise CleanError("private restore payload changed")
    content = _restore_content(receipt, stage)
    if _restore_cas(receipt, metadata, content) != expected:
        raise CleanError("private restore payload changed")
    _process_holds(stage)
    return metadata


def restore_preview(
    worktree_id: str, *, home: Path | None = None, trash_root: Path | None = None,
) -> dict[str, Any]:
    private_home = (home or Path.home()).resolve()
    receipt, _path = _load_trash_receipt(worktree_id, private_home)
    trash = Path(receipt["trash"])
    if trash_root is not None and trash.parent != _trash_directory(trash_root):
        raise CleanError("Trash receipt is outside the requested Trash root")
    target = Path(receipt["target"])
    trash = Path(receipt["trash"])
    if _real_absolute(target, "original path") != target or _real_absolute(trash, "Trash artifact") != trash:
        raise CleanError("original path contains a symlink")
    if receipt["state"] == "restored":
        return {"schema": "shadow.clean-restore.v1", "action": "already_restored", "changed": False, "receipt": worktree_id}
    if not trash.is_dir() or trash.is_symlink() or target.exists() or target.is_symlink():
        raise CleanError("Trash artifact or original path changed")
    metadata = trash.lstat()
    if (metadata.st_dev, metadata.st_ino) != (receipt["device"], receipt["inode"]):
        raise CleanError("Trash artifact changed after retirement")
    content = _restore_content(receipt, trash)
    source = Path(receipt["source_repo"])
    if not _registration_lock_state(source, target, worktree_id, receipt["manifest_sha256"]):
        raise CleanError("worktree is not locked by this retirement")
    _process_holds(trash)
    return {
        "schema": "shadow.clean-restore.v1", "action": "would_restore", "changed": False,
        "receipt": worktree_id, "cas": _restore_cas(receipt, metadata, content),
    }


def _registration_lock_state(source: Path, target: Path, worktree_id: str, manifest_digest: str) -> bool:
    """Return the exact lock state for the registered child, fail closed."""
    listing = _git(source, "worktree", "list", "--porcelain").stdout
    blocks = listing.split("\n\n")
    for block in blocks:
        lines = block.splitlines()
        if not lines or not lines[0].startswith("worktree "):
            continue
        if Path(lines[0][len("worktree "):]).resolve() != target.resolve():
            continue
        locks = [line[len("locked "):] for line in lines[1:] if line.startswith("locked ")]
        if not locks:
            return False
        if locks != [_lock_reason(worktree_id, manifest_digest)]:
            raise CleanError("worktree lock state changed")
        return True
    raise CleanError("worktree registration is missing")


def _authenticate_restore_registration(
    receipt: dict[str, Any], source: Path, target: Path, worktree_id: str, home: Path,
    *, require_lock: bool = True,
) -> bool:
    """Rebind source and target Git identities at the unlock boundary."""
    authenticated = [
        (created, journal) for created, journal in _valid_records(home)
        if created.get("receipt_sha256") == receipt.get("creation_receipt")
    ]
    if len(authenticated) != 1:
        raise CleanError("restore source provenance is unavailable")
    created, _journal = authenticated[0]
    if _source_identity(source) != created["source"]["repository"]:
        raise CleanError("restore source repository identity changed")
    common = Path(_git(target, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()).resolve()
    admin = Path(_git(target, "rev-parse", "--path-format=absolute", "--git-dir").stdout.strip()).resolve()
    if common != Path(created["git"]["common_dir"]).resolve() or admin != Path(created["git"]["admin_dir"]).resolve():
        raise CleanError("restore Git binding changed")
    source_common = Path(_git(source, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()).resolve()
    if source_common != common:
        raise CleanError("restore Git common directory changed")
    locked = _registration_lock_state(source, target, worktree_id, receipt["manifest_sha256"])
    if require_lock and not locked:
        raise CleanError("worktree is not locked by this retirement")
    return locked


def _relock_restore_registration(
    receipt: dict[str, Any], source: Path, target: Path, worktree_id: str, home: Path,
) -> None:
    """Re-lock only the exact authenticated registration after a mismatch."""
    locked = _authenticate_restore_registration(
        receipt, source, target, worktree_id, home, require_lock=False,
    )
    if not locked:
        _git(
            source, "worktree", "lock", "--reason",
            _lock_reason(worktree_id, receipt["manifest_sha256"]), "--", str(target),
        )
    _authenticate_restore_registration(receipt, source, target, worktree_id, home)


def _post_unlock_restore_check(
    receipt: dict[str, Any], source: Path, target: Path, worktree_id: str,
    home: Path, expected: str,
) -> None:
    """Revalidate content and Git provenance after the unlock mutation."""
    _validate_restored_target(receipt, target, expected)
    _authenticate_restore_registration(
        receipt, source, target, worktree_id, home, require_lock=False,
    )


def _load_restore_journal(path: Path, *, worktree_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except (CleanError, OSError, json.JSONDecodeError) as exc:
        raise CleanError("restore journal is malformed") from exc
    required = {"schema", "state", "worktree_id", "target", "trash", "private_stage", "source_race", "recovery_required", "device", "inode", "cas", "source_repo", "plan", "restore_cas"}
    if not isinstance(value, dict) or set(value) != required:
        raise CleanError("restore journal is malformed")
    if value["schema"] != RESTORE_JOURNAL_SCHEMA or value["worktree_id"] != worktree_id:
        raise CleanError("restore journal does not match this receipt")
    if value["target"] != receipt["target"] or value["trash"] != receipt["trash"] or value["device"] != receipt["device"] or value["inode"] != receipt["inode"] or value["source_repo"] != receipt["source_repo"] or value["plan"] != receipt["plan"]:
        raise CleanError("restore journal lineage changed")
    if Path(value["private_stage"]) != _private_stage_path(Path(value["trash"]).parent, worktree_id, receipt["manifest_sha256"]):
        raise CleanError("restore journal private stage lineage changed")
    if not isinstance(value["source_race"], bool) or not isinstance(value["recovery_required"], bool):
        raise CleanError("restore journal recovery state is malformed")
    if value["state"] not in {"prepared", "moved", "unlocking", "unlocked", "recovery_required"}:
        raise CleanError("restore journal state is unsupported")
    return value


def restore_apply(
    worktree_id: str, *, expected: str, home: Path | None = None,
    trash_root: Path | None = None, crash_at: str | None = None,
) -> dict[str, Any]:
    private_home = (home or Path.home()).resolve()
    receipt, receipt_path = _load_trash_receipt(worktree_id, private_home)
    if receipt.get("state") == "restored":
        directories = _clean_dirs(private_home, create=False)
        journal_path = directories["restore-journals"] / f"{receipt['creation_receipt']}.json"
        if journal_path.exists() or journal_path.is_symlink():
            pending = _load_restore_journal(journal_path, worktree_id=worktree_id, receipt=receipt)
            if pending["state"] != "unlocked":
                raise CleanError("restore journal is inconsistent")
            journal_path.unlink()
            _fsync_directory(journal_path.parent)
        return {"schema": "shadow.clean-restore.v1", "action": "already_restored", "changed": False, "receipt": worktree_id}
    target = Path(receipt["target"])
    trash = Path(receipt["trash"])
    if _real_absolute(target, "original path") != target or _real_absolute(trash, "Trash artifact") != trash:
        raise CleanError("restore path contains a symlink")
    if trash_root is not None and trash.parent != _trash_directory(trash_root):
        raise CleanError("Trash receipt is outside the requested Trash root")
    plan = Path(receipt["plan"])
    directories = _clean_dirs(private_home, create=True)
    journal_path = directories["restore-journals"] / f"{receipt['creation_receipt']}.json"
    with _board.project_lock(plan):
        _crash_point("restore_before_rename", crash_at)
        restore_journal = None
        if journal_path.exists() or journal_path.is_symlink():
            restore_journal = _load_restore_journal(journal_path, worktree_id=worktree_id, receipt=receipt)
        private_stage = Path(restore_journal["private_stage"]) if restore_journal is not None else None
        recovering = restore_journal is not None and target.is_dir() and not trash.exists() and not private_stage.exists()
        recovering_stage = restore_journal is not None and not target.exists() and private_stage is not None and private_stage.is_dir() and not trash.exists()
        if recovering:
            metadata = target.lstat()
            if (metadata.st_dev, metadata.st_ino) != (receipt["device"], receipt["inode"]):
                raise CleanError("restored worktree identity changed")
        elif recovering_stage:
            metadata = private_stage.lstat()
            if (metadata.st_dev, metadata.st_ino) != (receipt["device"], receipt["inode"]):
                raise CleanError("private restore payload changed")
        elif restore_journal is not None and restore_journal["state"] != "prepared":
            raise CleanError("restore transaction is inconsistent")
        else:
            if target.exists() or target.is_symlink() or not trash.is_dir() or trash.is_symlink():
                raise CleanError("Trash artifact or original path changed")
            metadata = trash.lstat()
        if (metadata.st_dev, metadata.st_ino) != (receipt["device"], receipt["inode"]):
            raise CleanError("Trash artifact changed after retirement")
        content = _restore_content(receipt, target if recovering else (private_stage if recovering_stage else trash))
        cas = _restore_cas(receipt, metadata, content)
        if cas != expected:
            raise CleanError("restore artifact changed since preview")
        _process_holds(target if recovering else (private_stage if recovering_stage else trash))
        if recovering or recovering_stage:
            source = Path(receipt["source_repo"])
            if recovering_stage:
                try:
                    _validate_restore_stage(receipt, private_stage, expected)
                    _atomic_move_noreplace(
                        private_stage, target,
                        expected_source=(receipt["device"], receipt["inode"]),
                    )
                    _fsync_directory(private_stage.parent)
                    _fsync_directory(target.parent)
                    _validate_restored_target(receipt, target, expected)
                except (CleanError, CleanMoveCommittedError):
                    _flag_restore_recovery(journal_path, restore_journal)
                    raise
                restore_journal = {**restore_journal, "state": "moved", "source_race": False, "recovery_required": False}
                _replace(journal_path, restore_journal)
            if restore_journal["state"] == "prepared":
                _replace(journal_path, {**restore_journal, "state": "moved"})
                restore_journal = {**restore_journal, "state": "moved"}
            if restore_journal["state"] == "moved":
                _replace(journal_path, {**restore_journal, "state": "unlocking"})
                restore_journal = {**restore_journal, "state": "unlocking"}
            if restore_journal["state"] == "unlocking":
                # Unlocking is a durable handoff point.  A crash can leave
                # either side committed, so authenticate the registration
                # without demanding a lock and unlock only when the exact
                # transaction-bound lock is still present.
                locked = _authenticate_restore_registration(
                    receipt, source, target, worktree_id, private_home, require_lock=False,
                )
                if locked:
                    _git(source, "worktree", "unlock", "--", str(target))
                _replace(journal_path, {**restore_journal, "state": "unlocked"})
                restore_journal = {**restore_journal, "state": "unlocked"}
            else:
                # An unlocked journal proves that the unlock already crossed
                # its mutation boundary.  Rebind the restored registration
                # but never issue a speculative second unlock.
                _authenticate_restore_registration(
                    receipt, source, target, worktree_id, private_home, require_lock=False,
                )
            _crash_point("restore_after_unlock", crash_at)
            try:
                _post_unlock_restore_check(receipt, source, target, worktree_id, private_home, expected)
            except CleanError:
                try:
                    _relock_restore_registration(receipt, source, target, worktree_id, private_home)
                except CleanError:
                    _flag_restore_recovery(journal_path, restore_journal, state="recovery_required")
                else:
                    _flag_restore_recovery(journal_path, restore_journal, state="moved")
                raise
            restored = {**receipt, "state": "restored", "restored_at": _stamp(datetime.now(timezone.utc))}
            restored["receipt_sha256"] = canonical_sha256({key: item for key, item in restored.items() if key != "receipt_sha256"})
            _replace(receipt_path, restored)
            return {"schema": "shadow.clean-restore.v1", "action": "restored", "changed": True, "receipt": worktree_id}
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise CleanError("original parent directory is unavailable")
        source = Path(receipt["source_repo"])
        if not _registration_lock_state(source, target, worktree_id, receipt["manifest_sha256"]):
            raise CleanError("worktree is not locked by this retirement")
        if restore_journal is None:
            private_stage = _create_private_stage(trash.parent, worktree_id, receipt["manifest_sha256"])
        elif private_stage.is_symlink() or (private_stage.exists() and not private_stage.is_dir()):
            raise CleanError("private restore payload is unsafe")
        restore_journal = restore_journal or {
            "schema": RESTORE_JOURNAL_SCHEMA, "state": "prepared", "worktree_id": worktree_id,
            "target": str(target), "trash": str(trash), "device": receipt["device"],
            "inode": receipt["inode"], "cas": receipt["cas"], "source_repo": str(source),
            "plan": str(plan), "restore_cas": expected, "private_stage": str(private_stage),
            "source_race": False, "recovery_required": False,
        }
        if journal_path.exists() is False:
            _exclusive(journal_path, restore_journal)
        try:
            if not private_stage.exists():
                _atomic_move_noreplace(
                    trash, private_stage,
                    expected_source=(receipt["device"], receipt["inode"]),
                )
                _crash_point("after_private_stage", crash_at)
            staged = _validate_restore_stage(receipt, private_stage, expected)
            _atomic_move_noreplace(
                private_stage, target,
                expected_source=(staged.st_dev, staged.st_ino),
            )
            _fsync_directory(private_stage.parent)
            _fsync_directory(target.parent)
            # Keep this identity/content boundary inside the move transaction.
            # A same-UID replacement after the native rename is a recovery
            # case, not evidence that the authenticated worktree was restored.
            _validate_restored_target(receipt, target, expected)
        except CleanMoveCommittedError:
            # The native rename committed but its filesystem sync did not.
            # Retain the prepared intent for authenticated retry; this is not
            # a content/provenance mismatch.
            raise
        except CleanError as exc:
            committed_target = False
            try:
                committed = target.lstat()
                committed_target = (
                    (committed.st_dev, committed.st_ino) ==
                    (receipt["device"], receipt["inode"])
                    and not trash.exists()
                    and not private_stage.exists()
                )
            except OSError:
                pass
            post_hop_mismatch = (
                not (private_stage.exists() or private_stage.is_symlink())
                and not (trash.exists() or trash.is_symlink())
                and (target.exists() or target.is_symlink())
            )
            if committed_target and "sync" in str(exc).lower():
                raise CleanMoveCommittedError(
                    "worktree restore committed; filesystem sync is incomplete"
                ) from exc
            if not post_hop_mismatch:
                # A pre-hop source or destination refusal remains its
                # original bounded diagnostic; the durable marker still
                # prevents a retry from being mistaken for a clean restore.
                _flag_restore_recovery(journal_path, restore_journal)
                raise
            # A raced or changed post-hop payload is never treated as a
            # committed restore. Preserve the journal, exact lock, and any
            # observed bytes for manual recovery, without issuing a receipt.
            _flag_restore_recovery(journal_path, restore_journal, state="recovery_required")
            raise CleanError("recovery required after restore source race") from exc
        _remove_empty_private_stage(private_stage)
        restore_journal = {**restore_journal, "state": "moved", "source_race": False, "recovery_required": False}
        _replace(journal_path, restore_journal)
        _crash_point("restore_after_rename", crash_at)
        restore_journal = {**restore_journal, "state": "unlocking"}
        _replace(journal_path, restore_journal)
        _crash_point("restore_after_unlocking", crash_at)
        _authenticate_restore_registration(receipt, source, target, worktree_id, private_home)
        _git(source, "worktree", "unlock", "--", str(target))
        restore_journal = {**restore_journal, "state": "unlocked"}
        _replace(journal_path, restore_journal)
        _crash_point("restore_after_unlock", crash_at)
        try:
            _post_unlock_restore_check(receipt, source, target, worktree_id, private_home, expected)
        except CleanError:
            try:
                _relock_restore_registration(receipt, source, target, worktree_id, private_home)
            except CleanError:
                _flag_restore_recovery(journal_path, restore_journal, state="recovery_required")
            else:
                _flag_restore_recovery(journal_path, restore_journal, state="moved")
            raise
        restored = {**receipt, "state": "restored", "restored_at": _stamp(datetime.now(timezone.utc))}
        restored["receipt_sha256"] = canonical_sha256({key: item for key, item in restored.items() if key != "receipt_sha256"})
        _replace(receipt_path, restored)
        _crash_point("restore_after_receipt", crash_at)
        journal_path.unlink(missing_ok=True)
        return {"schema": "shadow.clean-restore.v1", "action": "restored", "changed": True, "receipt": worktree_id}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow clean",
        description="Preview Shadow cleanup; prepare an exact manifest, apply it to recoverable Trash, or restore by receipt/CAS.",
        epilog="Default is zero-write preview. Apply requires --manifest/--expect/--by; restore preview is --restore --receipt and restore apply adds --apply --expect.",
    )
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--worktree", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--manifest")
    parser.add_argument("--expect")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--receipt")
    parser.add_argument(
        "--auto",
        choices=("enable", "disable", "status"),
        help="enable, disable, or inspect lifecycle-bound automatic Trash",
    )
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--entity")
    parser.add_argument("--row", "--checkpoint", dest="checkpoint")
    parser.add_argument("--by", dest="seat")
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--landed-ref", required=False)
    args = parser.parse_args(argv)
    home = _root().parent
    try:
        if args.auto is not None:
            operational = (
                args.repo, args.worktree, args.prepare, args.apply, args.manifest,
                args.expect, args.restore, args.receipt, args.create, args.entity,
                args.checkpoint, args.seat, args.ref != "HEAD", args.landed_ref,
            )
            if any(value not in (None, False) for value in operational):
                raise CleanError("--auto is mutually exclusive with cleanup operations")
            if args.auto == "status":
                result = automatic_status(home=home)
            else:
                changed = _write_automatic(args.auto == "enable", home=home)
                result = {
                    "schema": AUTOMATIC_SCHEMA,
                    "action": args.auto,
                    "automatic_trash": args.auto == "enable",
                    "changed": changed,
                }
        elif args.restore:
            if not args.receipt:
                raise CleanError("--restore requires --receipt")
            if args.apply:
                if not args.expect:
                    raise CleanError("--restore --apply requires --expect")
                result = restore_apply(args.receipt, expected=args.expect, home=home)
            else:
                result = restore_preview(args.receipt, home=home)
        elif args.apply:
            if not args.manifest or not args.expect or not args.seat:
                raise CleanError("--apply requires --manifest, --expect, and --by")
            result = apply_manifest(
                args.manifest, expected_sha256=args.expect, by=args.seat, home=home,
            )
        elif args.create:
            if not all((args.repo, args.worktree, args.entity, args.checkpoint, args.seat, args.landed_ref)):
                raise CleanError("--create requires --repo, --worktree, --entity, --row, --by, and --landed-ref")
            result = create_managed_worktree(
                args.repo, args.worktree, entity=args.entity, checkpoint=args.checkpoint,
                seat=args.seat, ref=args.ref, landed_ref=args.landed_ref, home=home,
            )
        elif args.prepare:
            if args.worktree is None:
                raise CleanError("--prepare requires --worktree")
            records = [
                (receipt, journal)
                for receipt, journal in _valid_records(home)
                if Path(receipt["worktree"]["path"]) == _real_absolute(args.worktree, "worktree")
            ]
            if not records:
                raise CleanError("not Shadow-created")
            receipt, journal = records[0]
            refusal = _preview_refusal(receipt, journal, home)
            if refusal is not None:
                raise CleanError(refusal)
            head = _git(Path(receipt["worktree"]["path"]), "rev-parse", "HEAD").stdout.strip()
            result = prepare_manifest({
                "worktree": {"path": receipt["worktree"]["path"], "head": head, "landed_ref": receipt["landed_ref"]},
                "entity": receipt["claim"]["entity"], "checkpoint": receipt["claim"]["checkpoint"],
                "creation_receipt": receipt["receipt_sha256"],
                "issuance_journal": receipt["issuance_journal_sha256"],
            }, home=home)
        else:
            result = preview(repo=args.repo, worktree=args.worktree, home=home)
        if args.create:
            result = {"schema": "shadow.clean-create.v1", "state": result["state"], "id": f"worktree@{result['receipt_sha256'][:12]}"}
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            if result.get("candidates"):
                for candidate in result["candidates"]:
                    print(f"{candidate['reason']}: {candidate['id']}")
            elif result.get("reason"):
                print(result["reason"])
            elif args.create and result.get("id"):
                print(f"issued: {result['id']}")
            elif result.get("state") == "prepared":
                print(f"prepared: {result['id']} cas:{result['cas']}")
            elif result.get("action") in {"enable", "disable", "status"}:
                state = "enabled" if result.get("automatic_trash") else "disabled"
                print(f"automatic cleanup: {state}")
            elif result.get("action") in {"trashed", "already_trashed", "restored", "already_restored", "would_restore"}:
                suffix = f" cas:{result['cas']}" if result.get("cas") else ""
                print(f"{result['action']}: {result.get('receipt', '')}{suffix}")
            else:
                print(result.get("explanation", "no eligible Shadow-created worktrees"))
        return 0
    except (CleanError, _board.BoardError) as exc:
        print(f"shadow clean: {_public_reason(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
