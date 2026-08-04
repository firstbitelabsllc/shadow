#!/usr/bin/env python3
"""Run one bounded Pilot Puppy task through a native coding host.

This is deliberately a thin transport seam. It does not choose a provider,
create a queue, accept a result, or write a durable plan. The caller supplies
one host, one clean worktree, one task file, and exact allowed paths. The host
must return one ``pilot-puppy.host-receipt.v1`` JSON fence; otherwise the attempt is
blocked or failed closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

from pilot_puppy_roster_lib import RosterError, load_roster, route_roster_sha256
from pilot_puppy_route_lib import ROUTE_SCHEMA, RoutePacketError, load_route_packet, route_sha256
from pilot_puppy_seat_lib import SeatError, load_seat_overlay, selector_for_route
from pilot_puppy_task_lib import TaskError, frozen_task_sha256
import pilot_puppy_telemetry as telemetry


PROBE_SCHEMA = "pilot-puppy.host-probe.v1"
ATTEMPT_SCHEMA = "pilot-puppy.host-attempt.v1"
HOST_RECEIPT_SCHEMA = "pilot-puppy.host-receipt.v1"
HOSTS = {"codex", "claude-code", "cursor"}
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
MAX_CAPTURE_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_SUMMARY_CHARS = 280
MAX_TEST_NAME_CHARS = 160
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# Known-private markers match anywhere: a mid-string `/Users/...` behind a
# backtick or parenthesis is still a private path.
PRIVATE_PATH_RE = re.compile(
    r"(?:~/|/Users/|/home/|/private/var/|file:///|[A-Za-z]:[\\/]|\\\\)",
    re.IGNORECASE,
)
ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\"'=])/(?!/)[A-Za-z0-9._-]+(?:/[^\s\"']*)?")
SECRET_SHAPE_RE = re.compile(
    r"(?:sk-(?:ant-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)


class HostError(ValueError):
    """A fail-closed host adapter error."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


class RouteReference:
    """One validated route plus private local data that must never be emitted."""

    __slots__ = ("public", "roster", "slot_id")

    def __init__(self, public: dict[str, Any], roster: dict[str, Any], slot_id: str) -> None:
        self.public = public
        self.roster = roster
        self.slot_id = slot_id


def identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise HostError("identifier_invalid", f"{label} must match the public identifier pattern")
    return value


def _scrub_detail(text: str) -> str:
    """Redact private paths, secret shapes, and control characters from
    adapter-written detail before it is persisted in a receipt."""

    clean = CONTROL_RE.sub(" ", text)
    clean = PRIVATE_PATH_RE.sub("<redacted-path>", clean)
    clean = SECRET_SHAPE_RE.sub("<redacted-secret>", clean)
    return clean


def resolve_binary(host: str, explicit: str | None) -> str:
    candidate = explicit or os.environ.get(f"PILOT_PUPPY_{host.upper().replace('-', '_')}_BIN")
    if candidate:
        path = Path(candidate).expanduser()
        if "/" in candidate:
            if not path.is_file() or not os.access(path, os.X_OK):
                raise HostError("host_unavailable", f"{host} executable is unavailable")
            return str(path.resolve())
        resolved = shutil.which(candidate)
    else:
        resolved = shutil.which(
            {"claude-code": "claude", "cursor": "cursor-agent"}.get(host, host)
        )
    if not resolved:
        raise HostError("host_unavailable", f"{host} executable is unavailable")
    return str(Path(resolved).resolve())


def run_probe(binary: str) -> tuple[int | None, str, bool]:
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "", False
    output = (result.stdout or result.stderr or "").strip()
    # Versions are diagnostic only. Keep them short and strip control bytes;
    # never include command paths, prompts, or provider output in the receipt.
    clean = " ".join(output.split())[:120]
    return result.returncode, clean, result.returncode == 0


def git_value(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostError("git_unavailable", f"cannot inspect worktree: {exc}") from exc
    if result.returncode != 0:
        raise HostError("git_unavailable", "worktree is not a readable Git checkout")
    return result.stdout.strip()


def exact_git_root(repo: Path) -> Path:
    root = Path(git_value(repo, "rev-parse", "--show-toplevel")).resolve()
    if root != repo.resolve():
        raise HostError("worktree_invalid", "--repo must be an exact Git worktree root")
    return root


def status_paths(repo: Path, *, include_ignored: bool = False) -> list[str]:
    command = ["git", "-C", str(repo), "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    if include_ignored:
        command.append("--ignored")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostError("git_unavailable", f"cannot read worktree status: {exc}") from exc
    if result.returncode != 0:
        raise HostError("git_unavailable", "cannot read worktree status")
    raw = result.stdout
    entries = [item for item in raw.split(b"\0") if item]
    paths: list[str] = []
    for entry in entries:
        if len(entry) < 4:
            raise HostError("git_status_invalid", "Git returned an invalid status record")
        if chr(entry[0]) in {"R", "C"} or chr(entry[1]) in {"R", "C"}:
            raise HostError("scope_violation", "renames are not accepted by the host packet")
        path = entry[3:].decode("utf-8", errors="strict")
        paths.append(path)
    return paths


def local_state_snapshot(repo: Path) -> dict[str, str]:
    state = repo / ".pilot-puppy"
    evidence = state / "evidence"
    if state.is_symlink() or evidence.is_symlink():
        raise HostError("worktree_unsealed", "project evidence path must not be a symlink")
    if not state.exists():
        return {}
    if not state.is_dir():
        raise HostError("worktree_unsealed", "project evidence state must be a directory")
    unexpected = [path for path in state.iterdir() if path.name != "evidence"]
    if unexpected:
        raise HostError("worktree_unsealed", "project state contains material outside evidence")
    if not evidence.exists():
        return {}
    if not evidence.is_dir():
        raise HostError("worktree_unsealed", "project evidence must be a directory")
    snapshot: dict[str, str] = {}
    for path in sorted(evidence.rglob("*")):
        relative = path.relative_to(repo).as_posix()
        if path.is_symlink() or not path.is_file():
            raise HostError("worktree_unsealed", "project evidence must contain regular files only")
        snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def normalize_allowed(repo: Path, values: list[str]) -> list[str]:
    if not values:
        raise HostError("allowed_paths_missing", "at least one exact allowed path is required")
    normalized: list[str] = []
    for raw in values:
        if not isinstance(raw, str) or not raw.strip() or "*" in raw or "?" in raw:
            raise HostError("allowed_path_invalid", "allowed paths must be nonempty exact paths")
        candidate = (repo / raw).resolve(strict=False)
        try:
            relative = candidate.relative_to(repo).as_posix()
        except ValueError as exc:
            raise HostError("allowed_path_escape", "allowed path escapes the worktree") from exc
        if relative in {"", "."} or relative.startswith("../"):
            raise HostError("allowed_path_invalid", "the worktree root is not an allowed path")
        if relative not in normalized:
            normalized.append(relative)
    return normalized


def path_allowed(path: str, allowed: list[str]) -> bool:
    return any(path == item or path.startswith(item.rstrip("/") + "/") for item in allowed)


def public_command_shape(host: str) -> list[str]:
    """Return the static, non-secret shape that may enter an attempt receipt.

    The actual native argv is built separately below.  In particular, an
    owner-local selector must never be constructed and then filtered out of a
    public receipt: this projection has no selector input at all.
    """

    if host == "codex":
        return [
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "-C",
            "--output-last-message",
        ]
    if host == "claude-code":
        return [
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--permission-mode",
            "acceptEdits",
            "--add-dir",
        ]
    if host == "cursor":
        return [
            "--print",
            "--output-format",
            "json",
            "--workspace",
            "--trust",
            "--force",
            "agent",
        ]
    raise HostError("host_unknown", f"unsupported host: {host}")


def selector_flag(host: str, selector: dict[str, str] | None) -> str | None:
    """Make one safe single-token native selector option, or no option at all."""

    if selector is None:
        return None
    kind = selector.get("kind")
    value = selector.get("value")
    if kind not in {"model", "profile"} or not isinstance(value, str):
        raise HostError("seat_unconfigured", "private seat configuration is invalid")
    if kind == "profile" and host != "codex":
        raise HostError("seat_unconfigured", "private seat configuration is invalid")
    # The selector library validates the value before this point.  Keeping it a
    # single argv item prevents a local value from becoming a second CLI option.
    return f"--{kind}={value}"


def launch_command(
    host: str,
    binary: str,
    repo: Path,
    final_message: Path,
    selector: dict[str, str] | None = None,
) -> list[str]:
    """Build the private native argv for one frozen task.

    All three native CLIs receive the frozen task on stdin. Cursor's current
    non-interactive CLI requires ``agent``; a local selector is deliberately
    inserted before that subcommand.  This argv never becomes an attempt field.
    """

    selector_option = selector_flag(host, selector)
    if host == "codex":
        command = [binary, "exec"]
        if selector_option is not None:
            command.append(selector_option)
        command.extend(
            [
                "--json",
                "--ephemeral",
                "--sandbox",
                "workspace-write",
                "-C",
                str(repo),
                "--output-last-message",
                str(final_message),
            ]
        )
        return command
    if host == "claude-code":
        command = [binary]
        if selector_option is not None:
            command.append(selector_option)
        command.extend(
            [
                "--print",
                "--output-format",
                "json",
                "--no-session-persistence",
                "--permission-mode",
                "acceptEdits",
                "--add-dir",
                str(repo),
            ]
        )
        return command
    if host == "cursor":
        command = [
            binary,
            "--print",
            "--output-format",
            "json",
            "--workspace",
            str(repo),
            "--trust",
            "--force",
        ]
        if selector_option is not None:
            command.append(selector_option)
        command.append("agent")
        return command
    raise HostError("host_unknown", f"unsupported host: {host}")


def command_shape(host: str, binary: str, repo: Path, final_message: Path) -> list[str]:
    """Compatibility helper for tests of the selector-free native argv."""

    return launch_command(host, binary, repo, final_message)


def host_prompt(task: str, task_id: str, allowed: list[str], task_sha256: str) -> str:
    paths = "\n".join(f"- {path}" for path in allowed)
    return f"""Execute this bounded coding task in the current worktree.

Task ID: {task_id}
Frozen task SHA-256: {task_sha256}
Allowed paths:
{paths}

Do not change any other path. Run the relevant tests. Finish by emitting exactly
one JSON object with this shape and no additional JSON objects:
{{"schema":"{HOST_RECEIPT_SCHEMA}","task_id":"{task_id}","status":"ok","summary":"short result summary","proof_ref":"bounded-proof","changed_paths":["one-allowed-relative-path"],"tests":[{{"name":"relevant-test","status":"pass"}}]}}

For a successful result, use the exact Task ID above and a lowercase proof_ref
identifier such as `bounded-proof`. Do not use spaces or prose for proof_ref.
If the task is blocked or fails, emit the same one object with status `blocked`
or `failed`, `proof_ref`: null, and no passing-test claim.

Frozen task:
{task}
"""


def _drain(stream: Any, state: dict[str, Any]) -> None:
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        state["bytes"] += len(chunk)
        state["tail"].extend(chunk)
        if len(state["tail"]) > MAX_CAPTURE_BYTES:
            del state["tail"][:-MAX_CAPTURE_BYTES]


def _stop(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return
    try:
        process.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    process.wait()


def _close_pipes(process: subprocess.Popen[bytes]) -> None:
    """Close parent-owned pipes after the drain threads have finished."""

    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except OSError:
            pass


def run_bounded(command: list[str], task: str, repo: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=repo,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return {"returncode": None, "timed_out": False, "launch_error": str(exc), "duration_s": 0.0, "stdout": b"", "stderr": b""}
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    stdout_state: dict[str, Any] = {"tail": bytearray(), "bytes": 0}
    stderr_state: dict[str, Any] = {"tail": bytearray(), "bytes": 0}
    threads = [
        threading.Thread(target=_drain, args=(process.stdout, stdout_state), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr_state), daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        process.stdin.write(task.encode("utf-8"))
        process.stdin.close()
    except OSError:
        _stop(process)
        for thread in threads:
            thread.join(timeout=2)
        _close_pipes(process)
        return {"returncode": process.returncode, "timed_out": False, "launch_error": "host stdin failed", "duration_s": round(time.monotonic() - started, 3), "stdout": bytes(stdout_state["tail"]), "stderr": bytes(stderr_state["tail"])}
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop(process)
    for thread in threads:
        thread.join(timeout=2)
    _close_pipes(process)
    return {
        "returncode": process.returncode,
        "timed_out": timed_out,
        "launch_error": None,
        "duration_s": round(time.monotonic() - started, 3),
        "stdout": bytes(stdout_state["tail"]),
        "stderr": bytes(stderr_state["tail"]),
        "stdout_bytes": stdout_state["bytes"],
        "stderr_bytes": stderr_state["bytes"],
    }


def json_objects(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(value: Any) -> None:
        if not isinstance(value, dict):
            return
        candidates.append(value)
        nested = value.get("result")
        if isinstance(nested, str) and nested != text:
            candidates.extend(json_objects(nested))

    for raw in JSON_FENCE_RE.findall(text):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        add(value)
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        add(value)
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError:
        value = None

    add(value)

    # Cursor's JSON envelope currently places the model's final response in a
    # string that may contain prose immediately before the receipt object. A
    # normal line/full-document parse cannot see that object; scan only for
    # syntactically valid JSON objects and keep the schema filter below as the
    # trust boundary. This does not accept arbitrary text as a receipt.
    decoder = json.JSONDecoder()
    offset = 0
    while True:
        start = text.find("{", offset)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            offset = start + 1
            continue
        add(value)
        offset = start + max(end, 1)

    unique = {
        json.dumps(item, sort_keys=True, separators=(",", ":")): item
        for item in candidates
        if item.get("schema") == HOST_RECEIPT_SCHEMA
    }
    return list(unique.values())


def extract_host_receipt(texts: list[str]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for text in texts:
        candidates.extend(json_objects(text))
    # Native JSON/stream output can repeat the same final object; identical
    # repeats are not ambiguous, but two different claims are fail-closed.
    unique = {json.dumps(item, sort_keys=True, separators=(",", ":")): item for item in candidates}
    if len(unique) != 1:
        raise HostError("host_receipt_missing", "host must emit exactly one pilot-puppy.host-receipt.v1 object")
    return next(iter(unique.values()))


def _private_selector_present(text: str, private_values: tuple[str, ...]) -> bool:
    """Detect an owner-local selector before any receipt field can retain it."""

    folded = text.casefold()
    for value in private_values:
        if not value:
            continue
        # Long selector strings are safe to reject as a plain substring; short
        # aliases use token boundaries so ordinary words do not false-positive.
        if len(value) >= 4 and value.casefold() in folded:
            return True
        boundary = r"(?<![A-Za-z0-9._:+,=\[\]-])" + re.escape(value) + r"(?![A-Za-z0-9._:+,=\[\]-])"
        if re.search(boundary, text, flags=re.IGNORECASE):
            return True
    return False


def _receipt_text(value: object, label: str, maximum: int, private_values: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise HostError("host_receipt_invalid", f"host receipt {label} is invalid")
    clean = value.strip()
    if not clean or len(clean) > maximum or any(ord(character) < 32 or ord(character) == 127 for character in clean):
        raise HostError("host_receipt_invalid", f"host receipt {label} is invalid")
    if _private_selector_present(clean, private_values):
        raise HostError("host_receipt_private", "host receipt attempted to retain private selector data")
    if PRIVATE_PATH_RE.search(clean) or ABSOLUTE_PATH_RE.search(clean):
        raise HostError("host_receipt_invalid", f"host receipt {label} contains a private path")
    if SECRET_SHAPE_RE.search(clean):
        raise HostError("host_receipt_invalid", f"host receipt {label} contains a secret-shaped value")
    return clean


def validate_host_receipt(
    raw: dict[str, Any], task_id: str, allowed: list[str], private_values: tuple[str, ...] = ()
) -> dict[str, Any]:
    expected_fields = {"schema", "task_id", "status", "summary", "proof_ref", "changed_paths", "tests"}
    if set(raw) != expected_fields:
        raise HostError("host_receipt_invalid", "host receipt fields are invalid")
    if raw.get("schema") != HOST_RECEIPT_SCHEMA:
        raise HostError("host_receipt_invalid", "host receipt schema is invalid")
    if raw.get("task_id") != task_id:
        raise HostError("host_receipt_invalid", "host receipt task id does not match the packet")
    status = raw.get("status")
    if status not in {"ok", "blocked", "failed"}:
        raise HostError("host_receipt_invalid", "host receipt status is invalid")
    summary = _receipt_text(raw.get("summary"), "summary", MAX_SUMMARY_CHARS, private_values)
    reported_paths = raw.get("changed_paths")
    if not isinstance(reported_paths, list) or any(not isinstance(item, str) for item in reported_paths):
        raise HostError("host_receipt_invalid", "host receipt changed_paths must be a string list")
    safe_paths: list[str] = []
    for path in reported_paths:
        if not path or any(ord(character) < 32 or ord(character) == 127 for character in path):
            raise HostError("host_receipt_invalid", "host receipt changed path is invalid")
        if _private_selector_present(path, private_values):
            raise HostError("host_receipt_private", "host receipt attempted to retain private selector data")
        if SECRET_SHAPE_RE.search(path):
            raise HostError("host_receipt_invalid", "host receipt changed path contains a secret-shaped value")
        candidate = Path(path)
        if (
            not path
            or CONTROL_RE.search(path)
            or re.match(r"^(?:[A-Za-z]:[\\/]|\\\\)", path)
            or candidate.is_absolute()
            or ".." in candidate.parts
            or not path_allowed(path, allowed)
        ):
            raise HostError("scope_violation", "host receipt reports a path outside the packet")
        safe_paths.append(path)
    tests = raw.get("tests")
    if not isinstance(tests, list) or any(not isinstance(item, dict) for item in tests):
        raise HostError("host_receipt_invalid", "host receipt tests must be an object list")
    safe_tests: list[dict[str, str]] = []
    for item in tests:
        if set(item) != {"name", "status"} or item.get("status") not in {"pass", "fail"}:
            raise HostError("host_receipt_invalid", "host receipt test is invalid")
        safe_tests.append(
            {
                "name": _receipt_text(item.get("name"), "test name", MAX_TEST_NAME_CHARS, private_values),
                "status": item["status"],
            }
        )
    proof_ref = raw.get("proof_ref")
    if status == "ok":
        identifier(proof_ref, "host proof_ref")
        if _private_selector_present(proof_ref, private_values):
            raise HostError("host_receipt_private", "host receipt attempted to retain private selector data")
        if not safe_tests or any(item["status"] != "pass" for item in safe_tests):
            raise HostError("proof_missing", "successful host receipt requires passing tests")
    elif proof_ref is not None:
        identifier(proof_ref, "host proof_ref")
        if _private_selector_present(proof_ref, private_values):
            raise HostError("host_receipt_private", "host receipt attempted to retain private selector data")
    return {
        "status": status,
        "summary": summary,
        "proof_ref": proof_ref,
        "changed_paths": sorted(set(safe_paths)),
        "tests": safe_tests,
    }


def write_json(path: str, payload: dict[str, Any], *, force: bool = False) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path == "-":
        sys.stdout.write(encoded)
        return
    destination_input = Path(path).expanduser()
    if destination_input.is_symlink():
        raise HostError("output_unsafe", "output symlinks are not allowed")
    destination = destination_input.resolve(strict=False)
    if destination.exists() and not force:
        raise HostError("output_exists", "output exists; use --force to replace it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".host-attempt.", dir=destination.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if force:
            os.replace(temporary_path, destination)
        else:
            try:
                os.link(temporary_path, destination)
            except FileExistsError:
                raise HostError("output_exists", "output exists; use --force to replace it") from None
    finally:
        temporary_path.unlink(missing_ok=True)


def validate_output_path(repo: Path, value: str) -> Path | None:
    if value == "-":
        return None
    state = repo / ".pilot-puppy"
    evidence = state / "evidence"
    if state.is_symlink() or evidence.is_symlink():
        raise HostError("output_unsafe", "project evidence path must not be a symlink")
    supplied = Path(value).expanduser()
    destination = (supplied if supplied.is_absolute() else repo / supplied).resolve(strict=False)
    try:
        destination.relative_to(evidence.resolve(strict=False))
    except ValueError as exc:
        raise HostError("output_unsafe", "host output must stay in .pilot-puppy/evidence") from exc
    return destination


def route_file_path(repo: Path, value: str) -> Path:
    """Constrain a route packet to one regular file inside project evidence."""

    state = repo / ".pilot-puppy"
    evidence = state / "evidence"
    if state.is_symlink() or evidence.is_symlink():
        raise HostError("route_invalid", "project evidence path must not be a symlink")
    supplied = Path(value).expanduser()
    candidate_input = supplied if supplied.is_absolute() else repo / supplied
    if candidate_input.is_symlink():
        raise HostError("route_invalid", "route packet must be a regular evidence file")
    candidate = candidate_input.resolve(strict=False)
    evidence_root = evidence.resolve(strict=False)
    try:
        candidate.relative_to(evidence_root)
    except ValueError as exc:
        raise HostError("route_invalid", "route packet must stay in project evidence") from exc
    if candidate.parent != evidence_root or candidate.suffix != ".json":
        raise HostError("route_invalid", "route packet must be one direct JSON evidence file")
    return candidate


def route_reference(
    args: argparse.Namespace, repo: Path, task_id: str, task_sha256: str, route_path: Path | None
) -> RouteReference | None:
    """Validate an optional explicit route before launching its selected host."""

    if route_path is None:
        return None
    try:
        packet = load_route_packet(route_path)
        current_roster = load_roster(args.roster_file)
    except (RoutePacketError, RosterError):
        raise HostError("route_invalid", "route packet or local roster is invalid") from None
    if packet["status"] == "manual":
        raise HostError("route_manual", "manual routes cannot launch a native host")
    if packet["status"] != "ready" or packet["selection"] is None:
        raise HostError("route_blocked", "route packet is not ready for native execution")
    binding = packet["binding"]
    if binding["task_id"] != task_id or binding["task_sha256"] != task_sha256:
        raise HostError("route_task_mismatch", "route packet does not match the frozen task")
    if (
        binding["roster_revision"] != current_roster["revision"]
        or binding["route_roster_sha256"] != route_roster_sha256(current_roster)
    ):
        raise HostError("route_stale", "route packet does not match the current local roster")
    selection = packet["selection"]
    if selection["host"] != args.host:
        raise HostError("route_host_mismatch", "route packet selected a different native host")
    # A roster validates unique role priorities, so this is one exact private
    # slot lookup without adding that slot ID to the public route packet.
    selected_slots = [
        slot
        for slot in current_roster["slots"]
        if slot["role"] == selection["role"]
        and slot["host"] == selection["host"]
        and slot["priority"] == selection["priority"]
        and slot["enabled"]
    ]
    if len(selected_slots) != 1:
        raise HostError("route_invalid", "route packet selection is not an enabled declared local slot")
    return RouteReference(
        public={
            "schema": ROUTE_SCHEMA,
            "sha256": route_sha256(packet),
            "role": selection["role"],
            "host": selection["host"],
            "priority": selection["priority"],
        },
        roster=current_roster,
        slot_id=selected_slots[0]["id"],
    )


def probe(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        binary = resolve_binary(args.host, args.binary)
        returncode, version, available = run_probe(binary)
        payload = {
            "schema": PROBE_SCHEMA,
            "host": args.host,
            "available": available,
            "binary_name": Path(binary).name,
            "version": version or None,
            "probe_exit_code": returncode,
            "execution": {"performed": False, "projection_only": True},
        }
        return payload, 0 if available else 1
    except HostError as exc:
        return {
            "schema": PROBE_SCHEMA,
            "host": args.host,
            "available": False,
            "blocked": {"kind": exc.kind, "detail": exc.detail},
            "execution": {"performed": False, "projection_only": True},
        }, 1


def run_attempt(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    started = time.monotonic()
    task_id = identifier(args.task_id, "task id")
    repo = Path(args.repo).expanduser().resolve()
    exact_git_root(repo)
    allowed = normalize_allowed(repo, args.allowed_path)
    destination = validate_output_path(repo, args.out)
    try:
        task, task_sha256 = frozen_task_sha256(Path(args.task_file).expanduser())
    except TaskError as exc:
        kind = "task_too_large" if "exceeds" in str(exc) else "task_unreadable"
        raise HostError(kind, str(exc)) from None
    route_path = route_file_path(repo, args.route_file) if args.route_file else None
    if args.seat_file and not args.use_seat:
        raise HostError("seat_not_enabled", "private seat configuration requires --use-seat")
    if args.use_seat and route_path is None:
        raise HostError("seat_requires_route", "private seat configuration requires a ready sealed route")
    if route_path is not None and destination is not None and route_path == destination:
        raise HostError("route_output_collision", "host output cannot replace the active route packet")
    route = route_reference(args, repo, task_id, task_sha256, route_path)
    selector: dict[str, str] | None = None
    if args.use_seat:
        if route is None:  # Guard the invariant above if this function is called directly.
            raise HostError("seat_requires_route", "private seat configuration requires a ready sealed route")
        try:
            selector = selector_for_route(
                load_seat_overlay(args.seat_file), route.roster, route.slot_id, args.host
            )
        except SeatError:
            raise HostError(
                "seat_unconfigured", "private seat configuration is unavailable or does not match the sealed route"
            ) from None
    prompt = host_prompt(task, task_id, allowed, task_sha256)
    state_before = local_state_snapshot(repo)
    before = status_paths(repo)
    source_changes = [path for path in before if path not in state_before]
    if source_changes:
        raise HostError("worktree_dirty", "host packet requires a clean assigned worktree")
    before_all = status_paths(repo, include_ignored=True)
    before_ignored = set(before_all) - set(before)
    unsafe_ignored = [
        path
        for path in before_ignored
        if not path_allowed(path, allowed)
        and path.rstrip("/") != ".pilot-puppy"
        and not path.startswith(".pilot-puppy/evidence/")
    ]
    if unsafe_ignored:
        raise HostError("worktree_unsealed", "ignored files outside the packet are not allowed")
    binary = resolve_binary(args.host, args.binary)
    with tempfile.TemporaryDirectory(prefix="pilot-puppy-host-") as temp_dir:
        final_message = Path(temp_dir) / "final-message.txt"
        command = launch_command(args.host, binary, repo, final_message, selector)
        result = run_bounded(command, prompt, repo, args.timeout_seconds)
        output_texts = [result.get("stdout", b"").decode("utf-8", errors="replace")]
        output_texts.append(result.get("stderr", b"").decode("utf-8", errors="replace"))
        if final_message.is_file() and not final_message.is_symlink() and final_message.stat().st_size <= MAX_RECEIPT_BYTES:
            output_texts.append(final_message.read_text(encoding="utf-8", errors="replace"))
        after_all = status_paths(repo, include_ignored=True)
        state_after = local_state_snapshot(repo)
        changed = sorted(
            set(before_all).symmetric_difference(after_all)
            | {path for path in set(state_before) | set(state_after) if state_before.get(path) != state_after.get(path)}
        )
        status = "failed"
        blocked_reason: dict[str, str] | None = None
        host_receipt: dict[str, Any] | None = None
        try:
            if result.get("timed_out"):
                raise HostError("host_timeout", "host exceeded the bounded execution timeout")
            if result.get("launch_error"):
                raise HostError("host_launch_failed", str(result["launch_error"]))
            if result.get("returncode") != 0:
                raise HostError("host_failed", "host exited non-zero")
            private_values = (selector["value"],) if selector is not None else ()
            host_receipt = validate_host_receipt(
                extract_host_receipt(output_texts), task_id, allowed, private_values
            )
            outside = [path for path in changed if not path_allowed(path, allowed)]
            if outside:
                raise HostError("scope_violation", "host changed a path outside the packet")
            reported_missing = [
                path
                for path in host_receipt["changed_paths"]
                if path not in changed and path not in before_ignored
            ]
            if reported_missing:
                raise HostError("host_receipt_invalid", "host receipt reports a path Git did not change")
            status = host_receipt["status"]
            changed = sorted(set(changed) | set(host_receipt["changed_paths"]))
            if status == "ok" and not host_receipt["proof_ref"]:
                raise HostError("proof_missing", "host returned success without proof")
        except HostError as exc:
            blocked_reason = {"kind": exc.kind, "detail": _scrub_detail(exc.detail)}
            status = "blocked" if exc.kind not in {"host_failed", "host_launch_failed", "host_timeout"} else "failed"
        payload = {
            "schema": ATTEMPT_SCHEMA,
            "revision": 1,
            "host": args.host,
            "task_id": task_id,
            "task_sha256": task_sha256,
            "status": status,
            "summary": (host_receipt or {}).get("summary"),
            "proof_ref": (host_receipt or {}).get("proof_ref"),
            "changed_paths": [_scrub_detail(path) for path in changed],
            "tests": (host_receipt or {}).get("tests", []),
            "host_exit_code": result.get("returncode"),
            "timed_out": bool(result.get("timed_out")),
            "duration_s": round(time.monotonic() - started, 3),
            "stdout_bytes": result.get("stdout_bytes", 0),
            "stderr_bytes": result.get("stderr_bytes", 0),
            "command_shape": public_command_shape(args.host),
            "blocked": blocked_reason,
            "unreviewed_claim": True,
            "accepted_by_lead": False,
            "projection_is_usage": False,
        }
        if route is not None:
            payload["route"] = route.public
    write_json("-" if destination is None else str(destination), payload, force=args.force)
    if destination is not None:
        telemetry.record_host(payload, allowed_path_count=len(allowed))
    return payload, 0 if status == "ok" else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pilot-puppy host", description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    probe_parser = sub.add_parser("probe", help="probe one native host without invoking it")
    probe_parser.add_argument("--host", choices=sorted(HOSTS), required=True)
    probe_parser.add_argument("--binary")
    probe_parser.add_argument("--json", action="store_true")
    probe_parser.set_defaults(handler=probe)
    run_parser = sub.add_parser("run", help="run one bounded packet through one native host")
    run_parser.add_argument("--host", choices=sorted(HOSTS), required=True)
    run_parser.add_argument("--binary")
    run_parser.add_argument("--repo", default=os.getcwd())
    run_parser.add_argument("--task-file", required=True)
    run_parser.add_argument("--task-id", required=True)
    run_parser.add_argument("--allowed-path", action="append", default=[])
    run_parser.add_argument("--route-file", help="optional bounded route packet inside .pilot-puppy/evidence")
    run_parser.add_argument("--roster-file", help="trusted local roster used to verify --route-file")
    run_parser.add_argument(
        "--use-seat",
        action="store_true",
        help="attach one private local selector to the exact route-selected native slot",
    )
    run_parser.add_argument("--seat-file", help="trusted private local selector overlay used only with --use-seat")
    run_parser.add_argument("--out", default="-")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--timeout-seconds", type=int, default=900)
    run_parser.add_argument("--json", action="store_true")
    run_parser.set_defaults(handler=run_attempt)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload, code = args.handler(args)
    except HostError as exc:
        payload = {
            "schema": PROBE_SCHEMA if args.command == "probe" else ATTEMPT_SCHEMA,
            "host": getattr(args, "host", None),
            "status": "blocked",
            "blocked": {"kind": exc.kind, "detail": exc.detail},
            "execution": {"performed": False, "projection_only": True},
        }
        code = 1
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif code:
        print(f"pilot-puppy host: {payload.get('blocked') or payload.get('status')}", file=sys.stderr)
    else:
        print(f"pilot-puppy host: {payload.get('host')} {payload.get('status') or 'available'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
