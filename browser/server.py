#!/usr/bin/env python3
"""
vidux browser — localhost web UI for viewing PLAN.md across the fleet.

Read-only viewer. Stdlib only. See projects/vidux-browser/PLAN.md.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from glob import glob
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEV_ROOT = Path(os.environ.get("VIDUX_DEV_ROOT", Path.home() / "Development"))
HOST = "127.0.0.1"
PORT = int(os.environ.get("VIDUX_BROWSER_PORT", "7191"))

BROWSER_DIR = Path(__file__).resolve().parent
STATIC_DIR = BROWSER_DIR / "static"
ARTIFACTS_DIR = BROWSER_DIR / "artifacts"

# Three known plan-layout conventions in Leo's fleet.
PLAN_GLOBS = [
    "*/ai/plans/*/PLAN.md",
    "*/vidux/*/PLAN.md",
    "*/projects/*/PLAN.md",
    "*/PLAN.md",
]

# Files to expose alongside PLAN.md when present.
# Note: PLAN.md, INBOX.md, investigations/, evidence/ are core /vidux per the
# canonical doctrine (DOCTRINE.md + guides/fleet-ops.md + guides/investigation.md
# + guides/evidence-format.md). PROGRESS.md as a separate file and ASK-LEO.md
# are Leo-fleet extensions; the browser surfaces them when present but does not
# require them — a clean canonical-vidux repo without those files still works.
SIBLING_FILES = ["PROGRESS.md", "INBOX.md", "ASK-LEO.md", "DOCTRINE.md", "README.md"]

# safe_resolve() whitelist. Any other filename under DEV_ROOT is rejected —
# without this gate, a malicious page could fetch /api/file?path=…/.env or
# …/.ssh/config from a browser tab on Leo's machine.
ALLOWED_PLAN_FILES = frozenset({"PLAN.md", *SIBLING_FILES})

HOT_DAYS = 7
STALE_DAYS = 30

ARTIFACT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ARTIFACT_MAX_BYTES = 1024 * 1024  # 1 MB cap on POSTed HTML
ARTIFACT_TITLE_RE = re.compile(
    r"<title>([^<]+)</title>|<h1[^>]*>([^<]+)</h1>", re.I
)


def discover_plans() -> list[dict]:
    """Walk DEV_ROOT and return one entry per PLAN.md found."""
    seen: set[Path] = set()
    plans: list[dict] = []
    for pattern in PLAN_GLOBS:
        for hit in glob(str(DEV_ROOT / pattern)):
            path = Path(hit).resolve()
            if path in seen:
                continue
            if "node_modules" in path.parts:
                continue
            seen.add(path)
            plans.append(plan_meta(path))
    plans.sort(key=lambda p: (-p["mtime"], p["repo"], p["slug"]))
    return plans


def plan_meta(path: Path) -> dict:
    rel = path.relative_to(DEV_ROOT)
    parts = rel.parts
    repo = parts[0]
    # Slug is the directory name containing PLAN.md, or "_root_" for repo-root plans.
    parent_dir = path.parent
    if parent_dir == DEV_ROOT / repo:
        slug = "_root_"
    else:
        slug = parent_dir.name
    mtime = path.stat().st_mtime
    age_days = (time.time() - mtime) / 86400
    if age_days <= HOT_DAYS:
        status = "hot"
    elif age_days <= STALE_DAYS:
        status = "stale"
    else:
        status = "cold"
    siblings = [f for f in SIBLING_FILES if (parent_dir / f).is_file()]
    purpose = extract_purpose(path)
    return {
        "repo": repo,
        "slug": slug,
        "path": str(path),
        "rel": str(rel),
        "size": path.stat().st_size,
        "mtime": mtime,
        "age_days": round(age_days, 1),
        "status": status,
        "siblings": siblings,
        "purpose": purpose,
    }


def extract_purpose(path: Path) -> str:
    """Pull the first non-heading paragraph under '## Purpose' for sidebar preview."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r"##\s+Purpose\s*\n+([^\n#].+?)(?=\n\s*\n|\n##|\Z)", text, re.S)
    if not m:
        # Fall back to first non-heading paragraph after the title.
        m = re.search(r"^#[^\n]*\n+([^\n#].+?)(?=\n\s*\n|\n##|\Z)", text, re.S | re.M)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()[:240]


def safe_resolve(raw: str) -> Path | None:
    """Allow only PLAN.md + known sibling files under DEV_ROOT.

    The whitelist is the read-only contract. node_modules paths are rejected
    even when the filename matches, since a stale fixture there shouldn't
    surface in the viewer.
    """
    try:
        p = Path(raw).resolve()
    except (OSError, ValueError):
        return None
    try:
        p.relative_to(DEV_ROOT)
    except ValueError:
        return None
    if "node_modules" in p.parts:
        return None
    if p.name not in ALLOWED_PLAN_FILES:
        return None
    if not p.is_file():
        return None
    return p


def safe_resolve_any(raw: str) -> Path | None:
    """safe_resolve() OR an .html artifact under ARTIFACTS_DIR. Read-only either way."""
    p = safe_resolve(raw)
    if p:
        return p
    try:
        candidate = Path(raw).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate.relative_to(ARTIFACTS_DIR.resolve())
    except ValueError:
        return None
    if candidate.suffix.lower() != ".html":
        return None
    if not candidate.is_file():
        return None
    return candidate


def discover_artifacts() -> list[dict]:
    """List ad-hoc HTML artifacts in ARTIFACTS_DIR, newest first."""
    if not ARTIFACTS_DIR.is_dir():
        return []
    items: list[dict] = []
    for path in ARTIFACTS_DIR.glob("*.html"):
        if not path.is_file():
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4096]
        except OSError:
            head = ""
        m = ARTIFACT_TITLE_RE.search(head)
        if m:
            raw_title = (m.group(1) or m.group(2) or "").strip()
            title = raw_title or path.stem
        else:
            title = path.stem
        st = path.stat()
        age_days = (time.time() - st.st_mtime) / 86400
        items.append({
            "slug": path.stem,
            "title": title[:200],
            "path": str(path),
            "size": st.st_size,
            "mtime": st.st_mtime,
            "age_days": round(age_days, 1),
        })
    items.sort(key=lambda a: -a["mtime"])
    return items


def write_artifact(slug: str, html: str) -> tuple[bool, str]:
    """Write an artifact. Returns (ok, message)."""
    if not ARTIFACT_SLUG_RE.match(slug):
        return False, "slug must match [a-z0-9][a-z0-9-]{0,63}"
    if len(html.encode("utf-8")) > ARTIFACT_MAX_BYTES:
        return False, f"html exceeds {ARTIFACT_MAX_BYTES} bytes"
    try:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        path = ARTIFACTS_DIR / f"{slug}.html"
        path.write_text(html, encoding="utf-8")
    except OSError as e:
        return False, f"write failed: {e}"
    return True, str(path)


class Handler(BaseHTTPRequestHandler):
    server_version = "viduxBrowser/0.1"

    def log_message(self, fmt, *args):  # noqa: N802 — stdlib override
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def do_GET(self):  # noqa: N802 — stdlib override
        url = urlparse(self.path)
        route = url.path
        qs = parse_qs(url.query)
        if route == "/" or route == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
        elif route.startswith("/static/"):
            name = route[len("/static/"):]
            self._serve_static(name)
        elif route == "/api/health":
            self._json({"ok": True, "dev_root": str(DEV_ROOT), "port": PORT,
                        "artifacts_dir": str(ARTIFACTS_DIR)})
        elif route == "/api/plans":
            self._json({"plans": discover_plans(), "dev_root": str(DEV_ROOT)})
        elif route == "/api/artifacts":
            self._json({"artifacts": discover_artifacts(),
                        "artifacts_dir": str(ARTIFACTS_DIR)})
        elif route == "/api/file":
            raw = (qs.get("path") or [""])[0]
            p = safe_resolve_any(raw)  # plans + artifacts
            if not p:
                self._send(403, "forbidden")
                return
            ctype = ("text/html; charset=utf-8" if p.suffix.lower() == ".html"
                     else "text/markdown; charset=utf-8")
            self._send_with_type(p.read_bytes(), ctype)
        else:
            self._send(404, "not found")

    def do_POST(self):  # noqa: N802 — stdlib override
        url = urlparse(self.path)
        if url.path == "/api/artifact":
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > ARTIFACT_MAX_BYTES + 1024:
                self._send(400, "missing or oversized body")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send(400, f"bad json: {e}")
                return
            slug = str(payload.get("slug", "")).strip()
            html = payload.get("html", "")
            if not isinstance(html, str):
                self._send(400, "html must be a string")
                return
            ok, msg = write_artifact(slug, html)
            if not ok:
                self._send(400, msg)
                return
            self._json({"ok": True, "slug": slug, "path": msg})
        else:
            self._send(404, "not found")

    def _serve_static(self, name: str, ctype: str | None = None):
        if not name:
            self._send(404, "not found")
            return
        try:
            candidate = (STATIC_DIR / name).resolve()
            candidate.relative_to(STATIC_DIR.resolve())
        except (OSError, ValueError):
            self._send(404, "not found")
            return
        if not candidate.is_file():
            self._send(404, f"static asset missing: {name}")
            return
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or guess_content_type(candidate.name))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_with_type(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send(self, code: int, msg: str):
        body = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def guess_content_type(name: str) -> str:
    if name.endswith(".html"):
        return "text/html; charset=utf-8"
    if name.endswith(".css"):
        return "text/css; charset=utf-8"
    if name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if name.endswith(".json"):
        return "application/json; charset=utf-8"
    if name.endswith(".svg"):
        return "image/svg+xml"
    return "application/octet-stream"


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    sys.stderr.write(f"vidux browser → {url}  (dev_root={DEV_ROOT})\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nstopped\n")
        server.server_close()


if __name__ == "__main__":
    main()
