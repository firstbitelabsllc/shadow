#!/usr/bin/env python3
"""Small loopback briefing server for repository-owned Shadow plans."""

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
from shadow_scrub_lib import PRIVATE_PATH_RE as DRIVE_PRIVATE_PATH_RE
from shadow_scrub_lib import SECRET_SHAPE_RE as DRIVE_SECRET_SHAPE_RE
import importlib.util as _ilu
_LINT_SPEC = _ilu.spec_from_file_location("shadow_lint", SCRIPTS / "shadow-lint.py")
shadow_lint = _ilu.module_from_spec(_LINT_SPEC)
_LINT_SPEC.loader.exec_module(shadow_lint)


PRODUCT = "Shadow"
STATIC = Path(__file__).resolve().parent / "static"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()
MAX_REQUEST_BYTES = 16 * 1024
MAX_PLAN_BYTES = 1_000_000
MAX_PLANS = 250
SKIP_DIRS = frozenset({".git", ".shadow", ".venv", "venv", "node_modules", "dist", "build"})
FIELD_RE = re.compile(r"^\s*-\s*([^:]+):\s*(.*?)\s*$")
TASK_RE = re.compile(r"^\s*-\s*\[([^]]+)]\s*(.*?)\s*$")
RECEIPT_MARKER_RE = re.compile(r"\s*\[receipt:[a-f0-9]{16}]\s*")
# Title safety reuses the canonical private-path and secret-shape gates so the
# browser filter is never weaker than the evidence filters guarding this rail.
UNSAFE_TITLE_RE = re.compile(
    f"(?:{DRIVE_PRIVATE_PATH_RE.pattern}|{DRIVE_SECRET_SHAPE_RE.pattern})",
    re.IGNORECASE,
)
# Board fields are closed vocabularies or title-gated text, so a plan line can
# never carry a path or secret onto the board projection.
PROJECT_VALUE_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
# Grammar v2 has two postures. Legacy v1 modes are lint-blocking, so they
# never earn a chip; the board shows the finding instead.
MODE_VALUE_RE = re.compile(r"^(?:explore|ship)$")
CHECKPOINT_STATES = ("pending", "in_progress", "blocked", "completed")
CHECKPOINT_ALIASES = {"x": "completed", "done": "completed", "working": "in_progress"}
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
    for line in section(text, "Brief"):
        match = FIELD_RE.match(line)
        if not match:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
        result[key] = match.group(2).strip()
    return result


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



def read_plan(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.name != "PLAN.md":
        raise BrowserError("plan must be a regular non-symlink PLAN.md")
    if path.stat().st_size > MAX_PLAN_BYTES:
        raise BrowserError("plan exceeds the bounded size limit")
    return path.read_text(encoding="utf-8")


def project_of(brief: dict[str, str], relative: str) -> str:
    raw = (brief.get("project") or "").strip().lower()
    if PROJECT_VALUE_RE.fullmatch(raw):
        return raw
    head = relative.split("/", 1)[0].lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", head).strip("-")[:32]
    return slug if PROJECT_VALUE_RE.fullmatch(slug) else "unassigned"


def mode_of(brief: dict[str, str]) -> str | None:
    raw = (brief.get("mode") or "").strip().lower()
    return raw if MODE_VALUE_RE.fullmatch(raw) else None


def milestone_of(brief: dict[str, str]) -> str | None:
    raw = " ".join((brief.get("milestone") or "").split())
    if not raw or UNSAFE_TITLE_RE.search(raw):
        return None
    return raw[:120]


def checkpoint_counts(text: str) -> dict[str, int] | None:
    lines = section(text, "Tasks")
    if not lines:
        return None
    counts = {state: 0 for state in CHECKPOINT_STATES}
    for line in lines:
        match = TASK_RE.match(line)
        if not match:
            continue
        state = match.group(1).strip().lower()
        state = CHECKPOINT_ALIASES.get(state, state)
        if state in counts:
            counts[state] += 1
    return counts


def lint_summary(text: str) -> dict[str, Any]:
    try:
        findings = shadow_lint.lint_plan(text)
    except Exception:
        return {"parse_ok": False, "blocking": 0, "warning": 0}
    return {
        "parse_ok": True,
        "blocking": sum(1 for f in findings if f["severity"] == "blocking"),
        "warning": sum(1 for f in findings if f["severity"] == "warning"),
    }


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
        "project": project_of(brief, relative),
        "mode": mode_of(brief),
        "milestone": milestone_of(brief),
        "tasks": checkpoint_counts(text),
        "lint": lint_summary(text),
        "outcome": outcome,
        "decision": decision,
        "briefing": chief,
        "contract_error": error,
    }


def discover_plans(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name
            for name in directories
            if name not in SKIP_DIRS
            and not name.startswith(".")
            # Worktree pools hold disposable lane copies of the same plans;
            # scanning them floods the plan cap with duplicates.
            and not name.endswith("-worktrees")
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
        "schema": "shadow.local-decision.v1",
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
    directory = repo / ".shadow" / "evidence"
    if (repo / ".shadow").is_symlink() or directory.is_symlink():
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
    server_version = "Shadow/1"

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
        if endpoint != "/api/decision":
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
            if not isinstance(payload, dict) or set(payload) != {"plan", "option_id", "revision"}:
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
        except (BrowserError, DecisionInputError) as exc:
            self._json(400, {"error": str(exc)})
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Never reflect raw exception text: an OSError carries the full
            # absolute path, and the browser must never receive paths.
            self._json(
                400,
                {"error": "Shadow could not read or update that plan on this computer."},
            )

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("SHADOW_BROWSER_QUIET") != "1":
            super().log_message(format, *args)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], root: Path) -> None:
        super().__init__(address, Handler)
        self.scan_root = root


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="shadow browse", description=__doc__)
    value.add_argument("--host", default=os.environ.get("SHADOW_BROWSER_HOST") or "127.0.0.1")
    value.add_argument("--port", type=int, default=os.environ.get("SHADOW_BROWSER_PORT") or "7191")
    value.add_argument(
        "--root",
        default=os.environ.get("SHADOW_DEV_ROOT") or str(Path.home() / "Development"),
    )
    value.add_argument("--no-open", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    global DEV_ROOT
    args = parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        print("shadow browse: host must be loopback", file=sys.stderr)
        return 2
    if not 0 <= args.port <= 65535:
        print("shadow browse: port is outside the valid range", file=sys.stderr)
        return 2
    DEV_ROOT = Path(args.root).expanduser().resolve()
    if not DEV_ROOT.is_dir():
        print("shadow browse: scan root is not a directory", file=sys.stderr)
        return 2
    server = Server((args.host, args.port), DEV_ROOT)
    actual = server.server_address[1]
    print(f"Shadow -> http://{args.host}:{actual}", file=sys.stderr, flush=True)
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
