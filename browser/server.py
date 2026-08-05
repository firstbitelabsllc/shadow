#!/usr/bin/env python3
"""Small loopback briefing server for repository-owned Pilot Puppy plans."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
from typing import Any
from urllib.parse import urlparse
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    from chief_of_staff import project_chief_of_staff
    from decision_mode import DecisionInputError, build_choice, project_decision, receive_choice
    from outcome_source import OutcomeSourceError, project_plan_outcome
except ModuleNotFoundError:
    from browser.chief_of_staff import project_chief_of_staff
    from browser.decision_mode import DecisionInputError, build_choice, project_decision, receive_choice
    from browser.outcome_source import OutcomeSourceError, project_plan_outcome
from pilot_puppy_drive_lib import DrivePacketError, extract_document, public_preview
from pilot_puppy_drive_lib import PRIVATE_PATH_RE as DRIVE_PRIVATE_PATH_RE
from pilot_puppy_drive_lib import SECRET_SHAPE_RE as DRIVE_SECRET_SHAPE_RE


PRODUCT = "Pilot Puppy"
STATIC = Path(__file__).resolve().parent / "static"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()
MAX_REQUEST_BYTES = 16 * 1024
MAX_PLAN_BYTES = 1_000_000
MAX_PLANS = 250
MAX_DRIVE_OUTPUT_BYTES = 64 * 1024
DRIVE_PREPARE_TIMEOUT_SECONDS = 30
# The CLI owns the real deadline: every bounded step (host run, proof) gets
# DRIVE_STEP_TIMEOUT_SECONDS, and the browser ceiling sits above the CLI's
# worst case (three lanes x two bounded steps) so the browser never kills a
# legitimately running drive out from under its own supervision.
DRIVE_STEP_TIMEOUT_SECONDS = 900
DRIVE_LAUNCH_TIMEOUT_SECONDS = 3 * 2 * DRIVE_STEP_TIMEOUT_SECONDS + 600
DRIVE_ACCEPT_TIMEOUT_SECONDS = 3 * 2 * DRIVE_STEP_TIMEOUT_SECONDS + 600
DRIVE_SESSION_RE = re.compile(r"^[0-9a-f]{32}$")
SKIP_DIRS = frozenset({".git", ".pilot-puppy", ".venv", "venv", "node_modules", "dist", "build"})
FIELD_RE = re.compile(r"^\s*-\s*([^:]+):\s*(.*?)\s*$")
TASK_RE = re.compile(r"^\s*-\s*\[([^]]+)]\s*(.*?)\s*$")
RECEIPT_MARKER_RE = re.compile(r"\s*\[receipt:[a-f0-9]{16}]\s*")
# Title safety reuses the canonical private-path and secret-shape gates so the
# browser filter is never weaker than the evidence filters guarding this rail.
UNSAFE_TITLE_RE = re.compile(
    f"(?:{DRIVE_PRIVATE_PATH_RE.pattern}|{DRIVE_SECRET_SHAPE_RE.pattern})",
    re.IGNORECASE,
)
ALLOWED_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
}

DEV_ROOT = Path.home() / "Development"


class BrowserError(ValueError):
    pass


def root_id(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]


def public_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if len(slug) < 3:
        slug = f"project-{slug or 'work'}"
    return slug[:64]


def section(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    target = f"## {name}".lower()
    start = next((index + 1 for index, line in enumerate(lines) if line.strip().lower() == target), None)
    if start is None:
        return []
    result = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        result.append(line)
    return result


def operator_brief(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in section(text, "Operator Brief"):
        match = FIELD_RE.match(line)
        if not match:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
        result[key] = match.group(2).strip()
    return result


def task_counts(text: str) -> dict[str, int]:
    counts = {"pending": 0, "in_progress": 0, "blocked": 0, "completed": 0}
    aliases = {"x": "completed", "done": "completed", "working": "in_progress"}
    for line in text.splitlines():
        match = TASK_RE.match(line)
        if not match:
            continue
        state = aliases.get(match.group(1).strip().lower(), match.group(1).strip().lower())
        if state in counts:
            counts[state] += 1
    return counts


def title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            clean = " ".join(line[2:].split())
            if clean and UNSAFE_TITLE_RE.search(clean) is None:
                return clean[:120]
    return public_id(fallback).replace("-", " ").title()


def latest_progress(text: str) -> str | None:
    rows = [line.strip()[2:] for line in section(text, "Progress") if line.strip().startswith("- ")]
    if not rows:
        return None
    return RECEIPT_MARKER_RE.sub(" ", rows[-1]).strip()[:280]


def drive_preview(text: str) -> dict[str, Any] | None:
    """Project a valid Drive Packet without exposing its instructions or scope."""

    try:
        document = extract_document(text)
    except DrivePacketError:
        return {"state": "needs_attention"}
    preview = public_preview(document)
    if preview is None:
        return None
    state = "ready" if preview["ready_count"] else "nothing_ready"
    return {
        "state": state,
        "ready_count": preview["ready_count"],
        "lanes": preview["lanes"],
    }


def read_plan(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.name != "PLAN.md":
        raise BrowserError("plan must be a regular non-symlink PLAN.md")
    if path.stat().st_size > MAX_PLAN_BYTES:
        raise BrowserError("plan exceeds the bounded size limit")
    return path.read_text(encoding="utf-8")


def plan_record(path: Path, root: Path) -> dict[str, Any]:
    text = read_plan(path)
    relative = path.relative_to(root).as_posix()
    brief = operator_brief(text)
    outcome = None
    decision = None
    chief = None
    error = None
    try:
        outcome = project_plan_outcome(brief)
        decision = project_decision(outcome)
        plan_summary = {"latest_change": latest_progress(text)} if latest_progress(text) else None
        chief = project_chief_of_staff(outcome, plan_brief=plan_summary)
    except (OutcomeSourceError, DecisionInputError) as exc:
        error = str(exc)
    return {
        "id": hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16],
        "path": relative,
        "title": title(text, path.parent.name),
        "tasks": task_counts(text),
        "outcome": outcome,
        "decision": decision,
        "briefing": chief,
        "drive": drive_preview(text),
        "contract_error": error,
    }


def discover_plans(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name for name in directories if name not in SKIP_DIRS and not name.startswith(".")
        )
        if "PLAN.md" not in files:
            continue
        path = Path(current) / "PLAN.md"
        try:
            records.append(plan_record(path, root))
        except (BrowserError, OSError, UnicodeError, ValueError):
            continue
        if len(records) >= MAX_PLANS:
            break
    rank = {"needs_you": 0, "blocked": 1, "working": 2, "not_delivered": 3, "finished_with_proof": 4}
    records.sort(
        key=lambda item: (
            rank.get((item.get("briefing") or {}).get("state"), 5),
            item["title"].lower(),
            item["path"],
        )
    )
    return records


def resolve_plan(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise BrowserError("plan path is required")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise BrowserError("plan path must be relative")
    root = root.resolve()
    candidate = root
    for part in relative.parts:
        candidate /= part
        if candidate.is_symlink():
            raise BrowserError("plan path must not contain symlinks")
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BrowserError("plan path escapes the scan root") from exc
    if candidate.name != "PLAN.md":
        raise BrowserError("plan path must name PLAN.md")
    read_plan(candidate)
    return candidate


def repository_root(plan: Path) -> Path:
    plan = plan.resolve()
    result = subprocess.run(
        ["git", "-C", str(plan.parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise BrowserError("plan is not inside a Git worktree")
    repo = Path(result.stdout.strip()).resolve()
    try:
        plan.relative_to(repo)
    except ValueError as exc:
        raise BrowserError("plan escapes its Git worktree") from exc
    return repo


def public_drive_session(value: object, *, action: str) -> dict[str, Any]:
    """Return only the browser-safe result of a foreground local Drive run."""

    fields = {"schema", "revision", "session_id", "state", "plan_sha256", "base_sha256", "lanes"}
    if not isinstance(value, dict) or set(value) != fields:
        raise BrowserError("Pilot Puppy could not safely read the local work update")
    session_id = value["session_id"]
    state = value["state"]
    lanes = value["lanes"]
    expected_state = {"prepare": "prepared", "launch": "finished", "accept": "accepted"}.get(action)
    if (
        value["schema"] != "pilot-puppy.drive-session.v1"
        or value["revision"] != 1
        or not isinstance(session_id, str)
        or DRIVE_SESSION_RE.fullmatch(session_id) is None
        or state != expected_state
        or not isinstance(lanes, list)
        or not 1 <= len(lanes) <= 3
    ):
        raise BrowserError("Pilot Puppy could not safely read the local work update")
    statuses: list[str] = []
    for lane in lanes:
        if not isinstance(lane, dict) or not isinstance(lane.get("status"), str):
            raise BrowserError("Pilot Puppy could not safely read the local work update")
        status = lane["status"]
        if action == "prepare" and status != "prepared":
            raise BrowserError("Pilot Puppy could not safely read the local work update")
        if action == "launch" and status not in {"passed", "needs_attention"}:
            raise BrowserError("Pilot Puppy could not safely read the local work update")
        if action == "accept" and (
            status != "passed"
            or lane.get("scope_ok") is not True
            or lane.get("proof_ok") is not True
            or not (
                lane.get("merge_ok") is True
                or (lane.get("merge") == "manual" and lane.get("merge_ok") is None)
            )
        ):
            raise BrowserError("Pilot Puppy could not safely read the local work update")
        statuses.append(status)
    return {
        "session": session_id,
        "state": state,
        "work_count": len(statuses),
        "finished_count": statuses.count("passed"),
        "needs_attention_count": statuses.count("needs_attention"),
    }


def run_drive_subprocess(command: list[str], repo: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run the drive CLI as its own process group; the browser kill is a backstop."""

    try:
        process = subprocess.Popen(
            command,
            cwd=repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        raise BrowserError("Pilot Puppy could not finish that local step. Nothing was sent anywhere.") from exc
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Backstop only: the CLI's own bounded step timeouts fire first in
        # normal operation. Stop the whole supervisor process group and say
        # honestly that the work was stopped, not that nothing happened.
        for stop_signal in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(process.pid), stop_signal)
            except (OSError, ProcessLookupError):
                break
            try:
                process.wait(timeout=10)
                break
            except subprocess.TimeoutExpired:
                continue
        raise BrowserError(
            "That local step ran past its time budget and was stopped. "
            "Review the plan and any kept branches before starting it again."
        ) from None
    return subprocess.CompletedProcess(command, process.returncode, stdout=stdout, stderr=stderr)


def run_drive_action(plan: Path, *, action: str, session_id: str | None = None) -> dict[str, Any]:
    """Use the checked-in local Drive command with a fixed, browser-safe packet."""

    if action not in {"prepare", "launch", "accept"}:
        raise BrowserError("Pilot Puppy cannot start that kind of work")
    repo = repository_root(plan)
    relative_plan = plan.relative_to(repo).as_posix()
    command = [
        sys.executable,
        str(SCRIPTS / "pilot-puppy-drive.py"),
        action,
        "--repo",
        str(repo),
        "--plan",
        relative_plan,
        "--json",
    ]
    timeout = DRIVE_PREPARE_TIMEOUT_SECONDS
    if action in {"launch", "accept"}:
        if not isinstance(session_id, str) or DRIVE_SESSION_RE.fullmatch(session_id) is None:
            raise BrowserError("Choose ready work before taking that step")
        command.extend(["--session", session_id])
        command.extend(["--timeout-seconds", str(DRIVE_STEP_TIMEOUT_SECONDS)])
        timeout = DRIVE_LAUNCH_TIMEOUT_SECONDS if action == "launch" else DRIVE_ACCEPT_TIMEOUT_SECONDS
    result = run_drive_subprocess(command, repo, timeout)
    expected_partial_result = action == "launch" and result.returncode == 1
    if (result.returncode and not expected_partial_result) or len(result.stdout.encode("utf-8")) > MAX_DRIVE_OUTPUT_BYTES:
        raise BrowserError("Pilot Puppy could not prepare or start this work safely. Nothing was sent anywhere.")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BrowserError("Pilot Puppy could not safely read the local work update") from exc
    projection = public_drive_session(payload, action=action)
    if session_id is not None and projection["session"] != session_id:
        raise BrowserError("Pilot Puppy could not safely read the local work update")
    return projection


def write_decision_receipt(plan: Path, document: dict[str, Any], option_id: Any, revision: Any) -> dict[str, Any]:
    plan = plan.resolve()
    if isinstance(revision, bool) or not isinstance(revision, int):
        raise BrowserError("revision must be an integer")
    choice = build_choice(document, option_id)
    choice["revision"] = revision
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = receive_choice(document, choice, updated_at=now)
    repo = repository_root(plan)
    relative_plan = plan.relative_to(repo).as_posix()
    core = {
        "schema": "pilot-puppy.local-decision.v1",
        "plan": relative_plan,
        "outcome_id": result["receipt"]["outcome_id"],
        "decision_id": result["receipt"]["ask_id"],
        "option_id": result["receipt"]["option_id"],
        "observed_revision": result["receipt"]["observed_revision"],
        "authority_revision": result["receipt"]["authority_revision"],
        "state": result["receipt"]["state"],
        "reason": result["receipt"]["reason"],
    }
    encoded_core = json.dumps(core, sort_keys=True, separators=(",", ":"))
    identifier = hashlib.sha256(encoded_core.encode("utf-8")).hexdigest()[:16]
    payload = {**core, "receipt_id": identifier, "recorded_at": now}
    directory = repo / ".pilot-puppy" / "evidence"
    if (repo / ".pilot-puppy").is_symlink() or directory.is_symlink():
        raise BrowserError("evidence path must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"decision-{identifier}.json"
    if destination.is_symlink():
        raise BrowserError("decision receipt must not be a symlink")
    if destination.exists():
        current = json.loads(destination.read_text(encoding="utf-8"))
        if current.get("receipt_id") != identifier:
            raise BrowserError("decision receipt collision")
        return current
    fd, temporary = tempfile.mkstemp(prefix=".decision.", dir=directory)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError:
            current = json.loads(destination.read_text(encoding="utf-8"))
            if current.get("receipt_id") != identifier:
                raise BrowserError("decision receipt collision")
            return current
    finally:
        temporary_path.unlink(missing_ok=True)
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "PilotPuppy/1"

    @property
    def scan_root(self) -> Path:
        return self.server.scan_root  # type: ignore[attr-defined]

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()

    def _send(self, status: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
        self._headers(status, content_type, len(body))
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, (json.dumps(value, sort_keys=True) + "\n").encode("utf-8"), "application/json")

    def _loopback(self) -> bool:
        return self.client_address[0] in {"127.0.0.1", "::1"}

    def _valid_host(self) -> bool:
        raw = self.headers.get("Host")
        if not raw:
            return False
        try:
            parsed = urlparse(f"//{raw}")
            port = parsed.port
        except ValueError:
            return False
        return (
            (parsed.hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}
            and port == self.server.server_address[1]
        )

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return False
        parsed = urlparse(origin)
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "http"
            and host in {"127.0.0.1", "localhost", "::1"}
            and parsed.port == self.server.server_address[1]
        )

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        if not self._loopback() or not self._valid_host():
            self._json(403, {"error": "loopback Host required"})
            return
        parsed = urlparse(self.path)
        if parsed.path in ALLOWED_STATIC:
            name, content_type = ALLOWED_STATIC[parsed.path]
            self._send(200, (STATIC / name).read_bytes(), content_type)
            return
        if parsed.path == "/api/health":
            self._json(
                200,
                {
                    "ok": True,
                    "product": PRODUCT,
                    "version": VERSION,
                    "root_id": root_id(self.scan_root),
                    "server_mtime_ns": Path(__file__).stat().st_mtime_ns,
                },
            )
            return
        if parsed.path == "/api/plans":
            self._json(200, {"product": PRODUCT, "plans": discover_plans(self.scan_root)})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        endpoint = urlparse(self.path).path
        if endpoint not in {"/api/decision", "/api/drive/prepare", "/api/drive/launch", "/api/drive/accept"}:
            self._json(404, {"error": "not found"})
            return
        if not self._loopback() or not self._valid_host() or not self._same_origin():
            self._json(403, {"error": "local changes require this loopback browser"})
            return
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"error": "application/json required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_REQUEST_BYTES:
            self._json(413, {"error": "request exceeds the bounded limit"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise BrowserError("request has unknown or missing fields")
            if endpoint == "/api/decision":
                if set(payload) != {"plan", "option_id", "revision"}:
                    raise BrowserError("decision request has unknown or missing fields")
                plan = resolve_plan(self.scan_root, payload["plan"])
                record = plan_record(plan, self.scan_root)
                if record["outcome"] is None:
                    raise BrowserError(record["contract_error"] or "plan has no typed Outcome")
                receipt = write_decision_receipt(
                    plan,
                    record["outcome"],
                    payload["option_id"],
                    payload["revision"],
                )
                self._json(200, {"ok": True, "receipt": receipt})
                return
            expected = {"plan"} if endpoint == "/api/drive/prepare" else {"plan", "session"}
            if set(payload) != expected:
                raise BrowserError("ready-work request has unknown or missing fields")
            plan = resolve_plan(self.scan_root, payload["plan"])
            if not self.server.drive_lock.acquire(blocking=False):  # type: ignore[attr-defined]
                raise BrowserError("Pilot Puppy is already getting work ready, starting it, or bringing it into the project. Please wait for that update.")
            try:
                if endpoint == "/api/drive/prepare":
                    drive = run_drive_action(plan, action="prepare")
                elif endpoint == "/api/drive/launch":
                    drive = run_drive_action(plan, action="launch", session_id=payload["session"])
                else:
                    drive = run_drive_action(plan, action="accept", session_id=payload["session"])
            finally:
                self.server.drive_lock.release()  # type: ignore[attr-defined]
            self._json(200, {"ok": True, "drive": drive})
        except (BrowserError, DecisionInputError) as exc:
            self._json(400, {"error": str(exc)})
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Never reflect raw exception text: an OSError carries the full
            # absolute path, and the browser must never receive paths.
            self._json(
                400,
                {"error": "Pilot Puppy could not read or update that plan on this computer."},
            )

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("PILOT_PUPPY_BROWSER_QUIET") != "1":
            super().log_message(format, *args)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], root: Path) -> None:
        super().__init__(address, Handler)
        self.scan_root = root
        self.drive_lock = threading.Lock()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="pilot-puppy browse", description=__doc__)
    value.add_argument("--host", default=os.environ.get("PILOT_PUPPY_BROWSER_HOST") or "127.0.0.1")
    value.add_argument("--port", type=int, default=os.environ.get("PILOT_PUPPY_BROWSER_PORT") or "7191")
    value.add_argument(
        "--root",
        default=os.environ.get("PILOT_PUPPY_DEV_ROOT") or str(Path.home() / "Development"),
    )
    value.add_argument("--no-open", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    global DEV_ROOT
    args = parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        print("pilot-puppy browse: host must be loopback", file=sys.stderr)
        return 2
    if not 0 <= args.port <= 65535:
        print("pilot-puppy browse: port is outside the valid range", file=sys.stderr)
        return 2
    DEV_ROOT = Path(args.root).expanduser().resolve()
    if not DEV_ROOT.is_dir():
        print("pilot-puppy browse: scan root is not a directory", file=sys.stderr)
        return 2
    server = Server((args.host, args.port), DEV_ROOT)
    actual = server.server_address[1]
    print(f"Pilot Puppy -> http://{args.host}:{actual}", file=sys.stderr, flush=True)
    if not args.no_open:
        address = f"http://{args.host}:{actual}"
        threading.Timer(0.2, lambda: webbrowser.open(address)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
