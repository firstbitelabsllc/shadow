#!/usr/bin/env python3
"""Inert, fail-closed post-commit seam for optional Huddle delivery.

This module deliberately owns no board mutation.  A missing Plan-B runtime is
normal: callers get an unavailable receipt and retain the status-pull path.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import sysconfig
import tempfile
import time
import uuid
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Mapping

import shadow_board_schema as board_schema
from shadow_process_lib import run_bounded_pipes

EVENT_SCHEMA = "shadow.huddle-delivery-event.v1"
EVENT_NAMES = frozenset({"huddle_changed", "round_opened", "resolution_available",
                         "remote_recovery_required"})
_HID = re.compile(r"hdl_[0-9a-f]{8}\Z")
_MAX_IO = 16 * 1024
_SESSION_RULE = "(deny syscall-unix (syscall-number SYS_setsid SYS_setpgid SYS_posix_spawn))"
_PROCESS_BOUNDARY_PROBE = '''import os,sys
for change in (os.setsid, lambda: os.setpgid(0, 0)):
    child = os.fork()
    if not child:
        try:
            change()
        except PermissionError:
            os._exit(0)
        os._exit(1)
    if os.waitpid(child, 0)[1] != 0:
        raise SystemExit(1)
for options in ({"setsid": True}, {"setpgroup": 0}):
    try:
        child = os.posix_spawn(sys.executable, [sys.executable, "-I", "-B", "-c", "pass"], {}, **options)
    except PermissionError:
        continue
    os.waitpid(child, 0)
    raise SystemExit(1)
print("session-boundary-enforced")
'''


class RunnerRefused(RuntimeError):
    """A runtime predicate was unsafe or cannot be enforced."""


@dataclass(frozen=True)
class RunnerInvocation:
    operation: str
    argv: tuple[str, ...]
    stdin: bytes
    cwd: Path
    env: Mapping[str, str]
    allowed_targets: tuple[object, ...]
    writable_fds: tuple[int, ...] = ()
    read_only_fds: tuple[int, ...] = ()
    fd_roles: Mapping[str, int] | None = None
    owned_fds: tuple[int, ...] = ()
    entry_path: Path | None = None
    entry_identity: tuple = ()
    capability_identity: tuple = ()
    target_identities: tuple = ()
    selected_contacts: tuple[Path, ...] = ()
    closed: bool = False

    def close(self) -> None:
        if self.closed:
            return
        object.__setattr__(self, "closed", True)
        for fd in self.owned_fds:
            try:
                os.close(fd)
            except OSError:
                pass


def validate_event(event: dict) -> dict:
    """Validate the frozen four-field notification, without accepting prose."""
    if not isinstance(event, dict) or set(event) != {"schema", "event", "huddle_id", "generation"}:
        raise ValueError("event must have exactly the frozen fields")
    if event["schema"] != EVENT_SCHEMA or not isinstance(event["event"], str) or event["event"] not in EVENT_NAMES:
        raise ValueError("unsupported delivery event")
    if not isinstance(event["huddle_id"], str) or not _HID.fullmatch(event["huddle_id"]):
        raise ValueError("invalid huddle id")
    if type(event["generation"]) is not int or event["generation"] <= 0:
        raise ValueError("invalid huddle generation")
    return event


@lru_cache(maxsize=1)
def confinement_backend() -> str | None:
    """Require native profile compilation, positive execution and self-denial.

    The profile-specific runner and descendant falsifiers are in the source
    acceptance suite. This tiny per-process probe prevents binary presence or
    an early crash from being mistaken for an enforcing host.
    """
    if sys.platform != "darwin":
        return None
    try:
        for name in ("/usr/bin/sandbox-exec", "/usr/bin/true", "/bin/cat"):
            info = Path(name).stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                return None
        with tempfile.TemporaryDirectory(prefix="shadow-huddle-admission-") as directory:
            sentinel = Path(directory).resolve() / "forbidden"
            sentinel.write_bytes(b"admission sentinel")
            sentinel.chmod(0o600)
            profile = '(version 1) (deny default) (allow file-read-data (literal "/")) '
            profile += '(allow process-exec (literal "/usr/bin/true") (literal "/bin/cat"))'
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory) as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(profile)
                stream.flush()
                def probe(command):
                    return run_bounded_pipes(("/usr/bin/sandbox-exec", "-f", stream.name, *command),
                        cwd=Path("/"), env={}, stdin=b"", timeout=2)
                positive = probe(("/usr/bin/true",))
                denied = probe(("/bin/cat", str(sentinel)))
            if (positive.returncode != 0 or positive.timed_out or positive.output_limited
                    or denied.returncode != 1 or denied.timed_out or denied.output_limited or denied.stdout):
                return None
        return "darwin-seatbelt"
    except (OSError, ValueError):
        return None


def _runtime(home: Path) -> Path:
    return home / ".shadow" / "runtime" / "huddle-delivery"


def _identity(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _path_literal(value: str) -> str:
    if (not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(c in value for c in ('"', "\\", "*", "?", "[", "]"))):
        raise RunnerRefused("unsafe confinement literal")
    return '"' + value + '"'


def _open_absolute(path: Path, *, directory: bool = False) -> int:
    """Follow no path component, including parents of the final target."""
    raw = str(path)
    _path_literal(raw)
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise RunnerRefused("noncanonical absolute path")
    cursor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, component in enumerate(path.parts[1:]):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
            if index < len(path.parts) - 2 or directory:
                flags |= os.O_DIRECTORY
            next_fd = os.open(component, flags, dir_fd=cursor)
            os.close(cursor)
            cursor = next_fd
        return cursor
    except BaseException:
        os.close(cursor)
        raise


def _read_regular(fd: int, *, limit: int) -> bytes:
    before = os.fstat(fd)
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
            or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_size > limit):
        raise RunnerRefused("unsafe bounded runtime file")
    chunks = []
    remaining = limit + 1
    while remaining:
        part = os.read(fd, min(65536, remaining))
        if not part:
            break
        chunks.append(part)
        remaining -= len(part)
    value = b"".join(chunks)
    if len(value) > limit or len(value) != before.st_size or _identity(before) != _identity(os.fstat(fd)):
        raise RunnerRefused("runtime file changed during bounded read")
    os.lseek(fd, 0, os.SEEK_SET)
    return value


def _native_target(path: Path) -> tuple:
    if len(str(path).encode("utf-8")) > 1024 or path.name.lower() in {
        "sh", "bash", "zsh", "fish", "env", "node", "ruby", "perl", "osascript", "swift"
    } or path.name.lower().startswith("python"):
        raise RunnerRefused("interpreter is not a provider target")
    fd = _open_absolute(path)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1
                or info.st_mode & 0o022 or not info.st_mode & 0o111
                or os.read(fd, 4) not in {b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",
                    b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe",
                    b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}):
            raise RunnerRefused("unsafe native executable target")
        if _identity(info) != _identity(os.fstat(fd)):
            raise RunnerRefused("native target changed")
        return _identity(info)
    finally:
        os.close(fd)


def _json(raw: bytes) -> dict:
    try:
        value = json.loads(raw, object_pairs_hook=board_schema._strict_json_object)
    except (UnicodeError, ValueError) as exc:
        raise RunnerRefused("invalid closed runtime JSON") from exc
    if not isinstance(value, dict):
        raise RunnerRefused("runtime JSON must be an object")
    return value


def _contact(value: dict, *, seat: str, current: dict, stored: bool, now: datetime) -> tuple[str, str]:
    fields = {"schema", "instance_nonce", "provider", "capability", "endpoint", "claim_keys"}
    if stored:
        fields |= {"seat", "registered_at", "refreshed_at", "expires_at"}
    if set(value) != fields or value["schema"] != "shadow.huddle-contact.v1" or not _valid_seat(seat):
        raise RunnerRefused("closed contact required")
    if stored:
        registered, refreshed, expires = (_utc(value[k]) for k in ("registered_at", "refreshed_at", "expires_at"))
        if value["seat"] != seat or not registered <= refreshed <= now < expires <= refreshed + timedelta(minutes=10):
            raise RunnerRefused("contact lease is not current")
    try:
        if str(uuid.UUID(value["instance_nonce"])) != value["instance_nonce"]:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise RunnerRefused("contact nonce is not canonical") from exc
    provider, capability, endpoint = value["provider"], value["capability"], value["endpoint"]
    if not isinstance(provider, str) or provider not in {"codex", "cmux", "grok"} or not isinstance(capability, str) or not _IDENTIFIER.fullmatch(capability):
        raise RunnerRefused("contact capability is invalid")
    endpoint_fields = {"codex": {"thread_id", "turn_id"}, "cmux": {"surface_uuid"}, "grok": {"endpoint_uri"}}
    if not isinstance(endpoint, dict) or set(endpoint) != endpoint_fields[provider]:
        raise RunnerRefused("contact endpoint fields are invalid")
    for scalar in endpoint.values():
        if (not isinstance(scalar, str) or not scalar or len(scalar.encode("utf-8")) > 512
                or board_schema.CONTROL.search(scalar) or board_schema.SECRET_SHAPE_RE.search(scalar)):
            raise RunnerRefused("contact endpoint is unsafe")
    if provider == "cmux":
        try:
            if str(uuid.UUID(endpoint["surface_uuid"])) != endpoint["surface_uuid"]:
                raise ValueError
        except ValueError as exc:
            raise RunnerRefused("contact surface is not canonical") from exc
    if provider == "grok":
        # No undocumented URI scheme or broad transport allowance is inferred.
        raise RunnerRefused("Grok endpoint scheme has no admitted transport")
    refs = value["claim_keys"]
    if not isinstance(refs, list) or len(refs) > 64:
        raise RunnerRefused("contact claim count is invalid")
    seen = set()
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"entity", "row", "claim_revision", "owner"}:
            raise RunnerRefused("contact claim key is not closed")
        if (not isinstance(ref["entity"], str) or not board_schema.ENTITY_ID.fullmatch(ref["entity"])
                or not isinstance(ref["row"], str) or not board_schema.ROW_ID.fullmatch(ref["row"])
                or type(ref["claim_revision"]) is not int or ref["claim_revision"] < 0 or ref["owner"] != seat):
            raise RunnerRefused("contact claim identity is invalid")
        key = tuple(ref[k] for k in ("entity", "row", "claim_revision", "owner"))
        if key in seen or key not in current:
            raise RunnerRefused("contact claim is stale or duplicated")
        seen.add(key)
    return provider, capability


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None:
        raise RunnerRefused("capability timestamp is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RunnerRefused("capability timestamp is invalid") from exc
    if parsed.tzinfo != timezone.utc or parsed.microsecond:
        raise RunnerRefused("capability timestamp is not canonical UTC")
    return parsed


_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")


def validate_capabilities(raw: bytes, *, now: datetime | None = None) -> tuple[dict, ...]:
    """Strictly parse the 16-KiB, ten-minute Plan-B capability descriptor.

    Parsing is intentionally independent of contacts: it establishes neither a
    recipient nor permission to launch one.
    """
    if len(raw) > _MAX_IO:
        raise RunnerRefused("capability descriptor exceeds 16 KiB")
    try:
        value = json.loads(raw, object_pairs_hook=board_schema._strict_json_object)
    except (UnicodeDecodeError, ValueError) as exc:
        raise RunnerRefused("malformed capability descriptor") from exc
    if not isinstance(value, dict) or set(value) != {"schema", "generated_at", "expires_at", "entries"} or value["schema"] != "shadow.huddle-provider-capabilities.v1":
        raise RunnerRefused("closed capability descriptor required")
    generated, expires = _utc(value["generated_at"]), _utc(value["expires_at"])
    current = now or datetime.now(timezone.utc)
    if generated > current or expires <= current or expires > generated + timedelta(minutes=10):
        raise RunnerRefused("capability descriptor is expired or future dated")
    entries = value["entries"]
    if not isinstance(entries, list) or len(entries) > 32:
        raise RunnerRefused("invalid capability entry count")
    pairs: set[tuple[str, str]] = set()
    normalized: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"provider", "capability", "transport", "target"}:
            raise RunnerRefused("closed capability entry required")
        provider, capability, transport, target = (entry["provider"], entry["capability"], entry["transport"], entry["target"])
        if not all(isinstance(v, str) and _IDENTIFIER.fullmatch(v) for v in (provider, capability)) or provider not in {"codex", "cmux", "grok"}:
            raise RunnerRefused("invalid capability identity")
        if (provider, capability) in pairs:
            raise RunnerRefused("duplicate provider capability")
        pairs.add((provider, capability))
        if not isinstance(transport, str) or transport not in {"exec", "local_ipc", "network"} or not isinstance(target, str) or "\x00" in target:
            raise RunnerRefused("invalid capability target")
        if transport == "exec":
            candidate = Path(target)
            _native_target(candidate)
        elif transport == "network":
            # Network cannot be exactly confined by the current generic runner.
            raise RunnerRefused("generic network target is unsupported")
        else:
            raise RunnerRefused("exact local IPC confinement is not admitted")
        normalized.append(dict(entry))
    return tuple(normalized)


def validate_runner_fds(fds: Mapping[str, int]) -> None:
    """The board is pathname-only, and never crosses the runner boundary."""
    # The interpreter must retain its already-verified code descriptor long
    # enough to open /dev/fd/N. It conveys code, never board authority.
    allowed = {"contacts_dir", "capabilities", "entrypoint"}
    for role, fd in fds.items():
        if role not in allowed or type(fd) is not int or fd < 0:
            raise RunnerRefused("board descriptor or unknown inherited descriptor")
        try:
            flags = fcntl_getfl(fd)
        except OSError as exc:
            raise RunnerRefused("invalid runner descriptor") from exc
        if role in {"capabilities", "entrypoint"} and flags & os.O_ACCMODE != os.O_RDONLY:
            raise RunnerRefused("writable read-only descriptor")
        info = os.fstat(fd)
        if role == "contacts_dir":
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise RunnerRefused("unsafe contacts descriptor")
        elif not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            raise RunnerRefused("unsafe read-only descriptor")


def fcntl_getfl(fd: int) -> int:
    import fcntl
    return fcntl.fcntl(fd, fcntl.F_GETFL)


def _unavailable(reason: str = "optional delivery adapter absent") -> dict[str, object]:
    return {"available": False, "reason": reason}


def _valid_seat(seat: object) -> bool:
    try:
        from shadow_board_schema import validate_owner
        validate_owner(seat)
        return True
    except Exception:
        return False


def _runner_board() -> dict:
    """Read the runner-fixed board afresh; callers cannot nominate a path."""
    raw_path = os.environ.get("SHADOW_HUDDLE_BOARD_PATH")
    if not raw_path or not os.path.isabs(raw_path):
        raise RunnerRefused("runner board path is unavailable")
    # The parent walked every component before confinement. Reopen the fixed
    # sandbox-authorized pathname, not parent directory handles which would
    # require granting directory enumeration. A redirected pathname outside
    # this literal allowance is still denied by the kernel.
    return _read_board(Path(raw_path), component_walk=False)


def _read_board(path: Path, *, component_walk: bool = True) -> dict:
    try:
        fd = (_open_absolute(path) if component_walk else
              os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC))
        try:
            return board_schema.decode_board_bytes(_read_regular(fd, limit=4 * 1024 * 1024))
        finally:
            os.close(fd)
    except (OSError, board_schema.BoardError) as exc:
        raise RunnerRefused("runner board unavailable or invalid") from exc


def read_huddle_snapshot(huddle_id: str, expected_generation: int) -> dict:
    if not isinstance(huddle_id, str) or not _HID.fullmatch(huddle_id) or type(expected_generation) is not int or expected_generation <= 0:
        raise RunnerRefused("invalid huddle snapshot request")
    board = _runner_board()
    for huddle in board.get("huddles", []):
        if huddle.get("id") == huddle_id and huddle.get("generation") == expected_generation:
            # A copy stops an optional child from changing the decoded authority.
            return json.loads(json.dumps(huddle))
    raise RunnerRefused("current huddle generation unavailable")


def read_current_claims() -> Mapping[tuple[str, str, int, str], Mapping[str, object]]:
    return _current_claims(_runner_board())


def _current_claims(board: dict) -> dict:
    result: dict[tuple[str, str, int, str], Mapping[str, object]] = {}
    for claim in board.get("claims", []):
        try:
            key = (claim["entity"], claim["row"], claim["claim_revision"], claim["owner"])
        except (KeyError, TypeError):
            raise RunnerRefused("invalid current claim")
        if not all(isinstance(v, str) for v in (key[0], key[1], key[3])) or type(key[2]) is not int:
            raise RunnerRefused("invalid current claim")
        result[key] = json.loads(json.dumps(claim))
    return result


def prepare_delivery_invocation(event: dict | None, *, operation: str, seat: str | None,
                                contact_input: bytes | None, repo_root: Path,
                                home: Path | None = None) -> RunnerInvocation | None:
    """Open no state opportunistically: unsafe/absent Plan B is unavailable."""
    root = Path(__file__).resolve().parent.parent
    if repo_root.resolve() != root:
        return None
    base = _runtime(home or Path.home())
    if operation == "event":
        if event is None:
            raise RunnerRefused("event operation requires event")
        validate_event(event)
        name, data = "shadow-huddle-deliver-event.py", json.dumps(event, separators=(",", ":")).encode()
        extra: tuple[str, ...] = ()
    elif operation == "contact_register":
        if not _valid_seat(seat):
            raise RunnerRefused("invalid registration seat")
        if not isinstance(contact_input, bytes) or len(contact_input) > _MAX_IO:
            raise RunnerRefused("invalid registration input")
        name, data, extra = "shadow-contact-register.py", contact_input, ("--seat", seat)
    else:
        raise RunnerRefused("unknown runner operation")
    opened = []
    try:
        def directory(path):
            fd = _open_absolute(path, directory=True)
            opened.append(fd)
            info = os.fstat(fd)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise RunnerRefused("unsafe runtime directory")
            return fd

        directory(base.parent.parent)
        directory(base.parent)
        extension_fd = directory(base)
        contacts_fd = directory(base.parent / "contacts")
        entry_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=extension_fd)
        opened.append(entry_fd)
        _read_regular(entry_fd, limit=256 * 1024)
        cap_fd = os.open("shadow-huddle-provider-capabilities.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=extension_fd)
        opened.append(cap_fd)
        caps = validate_capabilities(_read_regular(cap_fd, limit=_MAX_IO))
        board_path = base.parent.parent / "board.json"
        board = _read_board(board_path)
        current = _current_claims(board)
        now = datetime.now(timezone.utc)
        pairs = set()
        selected_contacts = []
        if operation == "contact_register":
            pairs.add(_contact(_json(data), seat=seat, current=current, stored=False, now=now))
        else:
            huddle = next((h for h in board.get("huddles", []) if h["id"] == event["huddle_id"]
                           and h["generation"] == event["generation"]), None)
            if huddle is None:
                return None
            eligible = {board_schema._claim_key(board_schema._terminal_ref(huddle, c))
                        for c in huddle["claims"]}
            resolution = huddle.get("resolution")
            if resolution and resolution.get("handoff"):
                successor = board_schema._terminal_ref(huddle, resolution["handoff"]["successor_claim"])
                eligible.add(board_schema._claim_key(successor))
            # Bound enumeration as well as individual file reads. No pruning or
            # repair is allowed in this read-only event path.
            with os.scandir(contacts_fd) as names:
                for index, entry in enumerate(names):
                    if index >= 256:
                        raise RunnerRefused("contact directory exceeds selection bound")
                    if not re.fullmatch(r"[0-9a-f-]{36}\.json", entry.name):
                        continue
                    fd = -1
                    try:
                        fd = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=contacts_fd)
                        contact = _json(_read_regular(fd, limit=8192))
                        pair = _contact(contact, seat=contact.get("seat"), current=current, stored=True, now=now)
                        if entry.name != contact["instance_nonce"] + ".json":
                            continue
                        keys = {tuple(c[k] for k in ("entity", "row", "claim_revision", "owner"))
                                for c in contact["claim_keys"]}
                        if keys & eligible:
                            pairs.add(pair)
                            selected_contacts.append((pair, base.parent / "contacts" / entry.name))
                    except (OSError, RunnerRefused, ValueError, TypeError, KeyError):
                        continue
                    finally:
                        if fd >= 0:
                            os.close(fd)
        selected = tuple(c for c in caps if (c["provider"], c["capability"]) in pairs)
        if not selected or (operation == "contact_register" and len(selected) != 1):
            return None
        targets = tuple(_native_target(Path(c["target"])) for c in selected)
        interpreter = _verified_interpreter()
        info = interpreter.stat()
        if info.st_uid not in {0, os.geteuid()} or info.st_mode & 0o022 or not stat.S_ISREG(info.st_mode):
            raise RunnerRefused("unsafe fixed interpreter")
        roles = {"entrypoint": entry_fd, "capabilities": cap_fd, "contacts_dir": contacts_fd}
        validate_runner_fds(roles)
        env = {"SHADOW_HUDDLE_BOARD_PATH": str(board_path),
               "SHADOW_HUDDLE_CONTACTS_DIR_FD": str(contacts_fd),
               "SHADOW_HUDDLE_CAPABILITIES_FD": str(cap_fd),
               "SHADOW_HUDDLE_ALLOWED_TARGET_DIGESTS": json.dumps([
                   hashlib.sha256(json.dumps(c, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                   for c in selected], separators=(",", ":"))}
        retained = (entry_fd, cap_fd, contacts_fd)
        invocation = RunnerInvocation(
            operation, (str(interpreter), "-I", "-B", f"/dev/fd/{entry_fd}") + extra,
            data, root, env, selected,
            writable_fds=(contacts_fd,) if operation == "contact_register" else (),
            read_only_fds=(entry_fd, cap_fd) + (() if operation == "contact_register" else (contacts_fd,)),
            fd_roles=roles, owned_fds=retained, entry_path=base / name,
            entry_identity=_identity(os.fstat(entry_fd)), capability_identity=_identity(os.fstat(cap_fd)),
            target_identities=targets,
            selected_contacts=tuple(path for pair, path in selected_contacts
                                    if any(pair == (c["provider"], c["capability"]) for c in selected)))
        opened[:] = [fd for fd in opened if fd not in retained]
        return invocation
    except (OSError, RunnerRefused, board_schema.BoardError, ValueError, TypeError, KeyError):
        return None
    finally:
        for fd in opened:
            os.close(fd)


def _launch_prepared_runner(invocation: RunnerInvocation, *, timeout_seconds: int) -> dict[str, object]:
    """Shared bounded launcher; callers reach it only after confinement admission."""
    validate_runner_fds(invocation.fd_roles or {})
    if len(invocation.stdin) > _MAX_IO:
        raise RunnerRefused("oversize runner input")
    result = _run_seatbelt(invocation, timeout_seconds=timeout_seconds)
    if result.timed_out:
        return _unavailable("runner_timeout")
    if result.output_limited or result.returncode:
        return _unavailable("runner_refused")
    try:
        output = json.loads(result.stdout, object_pairs_hook=board_schema._strict_json_object)
        if invocation.operation == "event":
            if not isinstance(output, list) or len(output) > 256:
                raise RunnerRefused("closed attempted receipts required")
            event = _json(invocation.stdin)
            for item in output:
                if (not isinstance(item, dict) or set(item) != {"adapter", "huddle_id", "idempotency_key",
                        "contact_nonce", "attempted_at", "outcome"} or item["huddle_id"] != event["huddle_id"]
                        or not isinstance(item["adapter"], str) or item["adapter"] not in {c["provider"] for c in invocation.allowed_targets}
                        or not isinstance(item["outcome"], str) or item["outcome"] not in {"accepted", "refused", "unsupported", "unhealthy"}
                        or not isinstance(item["idempotency_key"], str) or re.fullmatch(r"[0-9a-f]{64}", item["idempotency_key"]) is None
                        or str(uuid.UUID(item["contact_nonce"])) != item["contact_nonce"]):
                    raise RunnerRefused("invalid attempted receipt")
                _utc(item["attempted_at"])
        else:
            request = _json(invocation.stdin)
            if (not isinstance(output, dict) or set(output) != {"registered", "provider", "capability", "instance_nonce"}
                    or type(output["registered"]) is not bool
                    or any(output[k] != request[k] for k in ("provider", "capability", "instance_nonce"))):
                raise RunnerRefused("invalid registration receipt")
            return {"available": True, **output}
    except (ValueError, TypeError, AttributeError, RunnerRefused):
        return _unavailable("runner_refused")
    # Availability is not delivery, a bid, or an ownership receipt. Child
    # attempts stay ephemeral and cannot be returned as board authority.
    return {"available": True}


def _seatbelt_profile(invocation: RunnerInvocation) -> str:
    interpreter = Path(invocation.argv[0])
    stdlib = Path(sysconfig.get_path("stdlib")).resolve(strict=True)
    scripts = invocation.cwd / "scripts"
    files = {interpreter, invocation.entry_path,
             Path(invocation.env["SHADOW_HUDDLE_BOARD_PATH"]),
             invocation.entry_path.parent / "shadow-huddle-provider-capabilities.json",
             Path(sys.base_prefix).resolve() / "Python"}
    for name in ("shadow_huddle_event.py", "shadow_board_schema.py", "shadow_git.py",
                 "shadow_plan_grammar.py", "shadow_scrub_lib.py", "shadow_process_lib.py",
                 "shadow_contacts.py", "shadow_delivery.py"):
        files.add(scripts / name)
    files.update(Path(f"/dev/fd/{fd}") for fd in invocation.read_only_fds + invocation.writable_fds)
    files.update(Path(c["target"]) for c in invocation.allowed_targets)
    files.update(invocation.selected_contacts)
    metadata = {invocation.cwd, scripts, Path("/dev/fd")}
    for path in files | {stdlib}:
        metadata.update(path.parents)
    lines = ["(version 1)", "(deny default)",
             # Literal / is only the directory itself, not a subtree. dyld
             # requires it even to launch /usr/bin/true on this macOS host.
             '(allow file-read-data (literal "/"))',
             "(allow process-fork)",
             # Process groups alone are not containment: forked children could
             # setsid/setpgid, and posix_spawn can change groups in the kernel.
             # Keep fork/exec for the exact selected native target, deny all
             # session-changing doors, and self-probe this rule before launch.
             _SESSION_RULE]
    for path in sorted(files):
        lines.append(f"(allow file-read* (literal {_path_literal(str(path))}))")
    for path in sorted(metadata):
        lines.append(f"(allow file-read-metadata (literal {_path_literal(str(path))}))")
    # FileFinder enumerates the one fixed module directory. This literal
    # grants no data read on any unlisted module inside it.
    lines.append(f"(allow file-read-data (literal {_path_literal(str(scripts))}))")
    lines.append(f"(allow file-read* (subpath {_path_literal(str(stdlib))}))")
    lines.append(f"(deny file-read* (subpath {_path_literal(str(stdlib / 'site-packages'))}))")
    for path in (interpreter, *(Path(c["target"]) for c in invocation.allowed_targets)):
        lines.append(f"(allow process-exec (literal {_path_literal(str(path))}))")
    contacts = invocation.entry_path.parent.parent / "contacts"
    if invocation.operation == "contact_register":
        lines.append(f"(allow file-read* (subpath {_path_literal(str(contacts))}))")
        lines.append(f"(allow file-write* (subpath {_path_literal(str(contacts))}))")
    else:
        # The retained directory permits bounded enumeration, not reading an
        # unrelated endpoint. Only selected contact files are readable above.
        lines.append(f"(allow file-read* (literal {_path_literal(str(contacts))}))")
    return "\n".join(lines) + "\n"


def _verified_interpreter() -> Path:
    interpreter = Path(sys.executable).resolve(strict=True)
    # Framework Python's bin shim posix_spawns this exact binary. Use the
    # verified framework interpreter directly instead of granting a second
    # general executable path to the untrusted child.
    if sys.platform == "darwin" and "Python.framework" in interpreter.parts:
        framework = Path(sys.base_prefix).resolve(strict=True)
        native = framework / "Resources/Python.app/Contents/MacOS/Python"
        if native.is_file():
            interpreter = native.resolve(strict=True)
    return interpreter


def _run_seatbelt(invocation: RunnerInvocation, *, timeout_seconds: float):
    if invocation.closed:
        raise RunnerRefused("runner descriptors are already closed")
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 2):
        raise RunnerRefused("runner deadline must be positive and at most two seconds")
    started = time.monotonic()
    roles = invocation.fd_roles or {}
    validate_runner_fds(roles)
    if (_identity(os.fstat(roles["entrypoint"])) != invocation.entry_identity
            or _identity(os.fstat(roles["capabilities"])) != invocation.capability_identity
            or tuple(_native_target(Path(c["target"])) for c in invocation.allowed_targets) != invocation.target_identities):
        raise RunnerRefused("runtime identity changed before launch")
    profile = _seatbelt_profile(invocation)
    # This is disposable launcher data, never board or optional runtime state.
    with tempfile.NamedTemporaryFile(prefix="shadow-huddle-seatbelt-", mode="w", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(profile)
        stream.flush()
        probe = run_bounded_pipes(("/usr/bin/sandbox-exec", "-f", stream.name,
                                   invocation.argv[0], "-I", "-B", "-c", _PROCESS_BOUNDARY_PROBE),
                                  cwd=invocation.cwd, env={}, stdin=b"", timeout=timeout_seconds,
                                  max_output_bytes=_MAX_IO)
        if (probe.returncode or probe.timed_out or probe.output_limited
                or probe.stdout != b"session-boundary-enforced\n"):
            raise RunnerRefused("unsupported process containment")
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise RunnerRefused("runner admission exhausted deadline")
        # /dev/fd opens share the retained open-file description and offset.
        # A repeated invocation must execute the same code, not an EOF script.
        for role in ("entrypoint", "capabilities"):
            os.lseek(roles[role], 0, os.SEEK_SET)
        return run_bounded_pipes(("/usr/bin/sandbox-exec", "-f", stream.name, *invocation.argv),
                                 cwd=invocation.cwd, env=invocation.env, stdin=invocation.stdin,
                                 pass_fds=invocation.writable_fds + invocation.read_only_fds,
                                 timeout=remaining, max_output_bytes=_MAX_IO)


def run_confined_event_runner(event: dict, *, repo_root: Path, home: Path | None = None,
                              timeout_seconds: int = 2) -> dict[str, object]:
    validate_event(event)
    if confinement_backend() is None:
        return _unavailable("unsupported_confinement")
    invocation = prepare_delivery_invocation(event, operation="event", seat=None,
                                             contact_input=None, repo_root=repo_root, home=home)
    if invocation is None:
        return _unavailable()
    try:
        return _launch_prepared_runner(invocation, timeout_seconds=timeout_seconds)
    except (OSError, RunnerRefused, ValueError):
        return _unavailable("runner_refused")
    finally:
        invocation.close()


def contact_register_unavailable(*, seat: str, stdin: bytes, repo_root: Path) -> dict[str, object]:
    if not _valid_seat(seat) or not isinstance(stdin, bytes) or len(stdin) > _MAX_IO:
        raise RunnerRefused("invalid registration request")
    return _unavailable()


def run_confined_contact_register(*, seat: str, stdin: bytes, repo_root: Path,
                                  home: Path | None = None, timeout_seconds: int = 2) -> dict[str, object]:
    if not _valid_seat(seat) or not isinstance(stdin, bytes) or len(stdin) > _MAX_IO:
        return _unavailable("runner_refused")
    if confinement_backend() is None:
        return _unavailable("unsupported_confinement")
    invocation = prepare_delivery_invocation(None, operation="contact_register", seat=seat,
                                             contact_input=stdin, repo_root=repo_root, home=home)
    if invocation is None:
        return _unavailable()
    try:
        return _launch_prepared_runner(invocation, timeout_seconds=timeout_seconds)
    except (OSError, RunnerRefused, ValueError):
        return _unavailable("runner_refused")
    finally:
        invocation.close()


def emit_post_commit(event: dict | None, *, repo_root: Path, home: Path | None = None) -> None:
    if event is not None:
        run_confined_event_runner(validate_event(event), repo_root=repo_root, home=home)


def post_commit_mutation(mutation: object, *, repo_root: Path, home: Path | None = None) -> object:
    """Post-lock best effort only; no transport failure changes core outcome."""
    if not getattr(mutation, "changed", False) or getattr(mutation, "event", None) is None:
        return mutation
    try:
        options = {} if home is None else {"home": home}
        emit_post_commit(getattr(mutation, "event"), repo_root=repo_root, **options)
    except (OSError, RunnerRefused, ValueError):
        pass
    return mutation
