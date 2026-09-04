#!/usr/bin/env python3
"""Shadow-managed worktree provenance and read-only cleanup preview.

This module deliberately has no Trash or removal operation.  A worktree is a
cleanup candidate only when Shadow itself created it and the creation's
pending-to-issued journal can authenticate the immutable receipt.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
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


class CleanError(ValueError):
    """A provenance or preview request is unsafe or stale."""


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
    result = {name: root / name for name in ("receipts", "journals", "manifests")}
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


def preview(*, repo: Path | None = None, worktree: Path | None = None, home: Path | None = None) -> dict[str, Any]:
    """Return a zero-write public projection of issued Shadow worktrees."""
    narrowed = _real_absolute(Path(worktree), "worktree") if worktree is not None else None
    candidates: list[dict[str, Any]] = []
    for receipt, journal in _valid_records(home):
        path = Path(receipt["worktree"]["path"])
        if narrowed is not None and path != narrowed:
            continue
        if repo is not None and Path(journal["source_repo"]).resolve() != _real_absolute(Path(repo), "repository"):
            continue
        candidates.append({
            "id": f"worktree@{receipt['receipt_sha256'][:12]}",
            "state": "eligible",
            "reason": "eligible",
            "entity": receipt["claim"]["entity"],
            "checkpoint": receipt["claim"]["checkpoint"],
        })
    report: dict[str, Any] = {
        "schema": "shadow.clean-preview.v1",
        "action": "preview",
        "changed": False,
        "explanation": "preview is zero-write; no repository, board, plan, manifest, Git, or Trash state changes",
        "candidates": candidates,
    }
    if narrowed is not None and not candidates:
        report["reason"] = "not Shadow-created"
    return report


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
    return {
        "schema": CLEAN_MANIFEST_SCHEMA,
        "generated_at": _stamp(now),
        "expires_at": _stamp(now + timedelta(minutes=15)),
        "target": {"kind": "worktree", "path": path, "head": head, "landed_ref": landed_ref},
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
    payload = _manifest_payload(candidate, now=current)
    digest = canonical_sha256(payload)
    path = directories["manifests"] / f"{digest}.json"
    _exclusive(path, payload)
    return path, payload, digest


def prepare_manifest(candidate: dict[str, Any], *, home: Path | None = None, now: str | datetime | None = None) -> dict[str, Any]:
    """Write the canonical private manifest and return only opaque metadata."""
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
    digest = canonical_sha256(manifest)
    if expected_sha256 is not None and digest != expected_sha256:
        raise CleanError("manifest changed since preview")
    return digest


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
            continue
        if digest.startswith(match.group(1)):
            matches.append((manifest, digest, path))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise CleanError("manifest identity is ambiguous")
    raise CleanError("manifest identity is unknown or expired")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shadow clean", description="Preview Shadow-managed worktree cleanup.")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--worktree", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--entity")
    parser.add_argument("--row", "--checkpoint", dest="checkpoint")
    parser.add_argument("--by", dest="seat")
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--landed-ref", required=False)
    args = parser.parse_args(argv)
    home = _root().parent
    try:
        if args.create:
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
            else:
                print(result.get("explanation", "no eligible Shadow-created worktrees"))
        return 0
    except (CleanError, _board.BoardError) as exc:
        print(f"shadow clean: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
