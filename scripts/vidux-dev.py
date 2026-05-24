#!/usr/bin/env python3
"""
vidux-dev — foreground vidux-browse with auto-restart on browser/ changes.

Polls $VIDUX_ROOT/browser/ via os.stat every VIDUX_DEV_POLL_INTERVAL seconds.
On any file add/change/remove, SIGTERMs the running vidux-browse child and
restarts it. SIGINT (ctrl-c) and SIGTERM are forwarded to the child for clean
shutdown.

Stdlib-only. Mental model matches `npm run dev` for a JS app: ctrl-c stops,
edits trigger reload.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(
    os.environ.get("VIDUX_ROOT", str(Path.home() / "Development" / "vidux"))
).expanduser().resolve()
BROWSE = ROOT / "bin" / "vidux-browse"
WATCH = ROOT / "browser"
POLL = float(os.environ.get("VIDUX_DEV_POLL_INTERVAL", "0.5"))

# Excluded dirs/extensions — avoid restart loops from cache / log / artifact churn.
EXCLUDE_DIR_PARTS = {"__pycache__", ".pytest_cache", "node_modules", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".swp", ".tmp"}


def _included(path: Path) -> bool:
    if any(part in EXCLUDE_DIR_PARTS for part in path.parts):
        return False
    if path.suffix in EXCLUDE_SUFFIXES:
        return False
    return True


def snapshot(root: Path) -> dict[str, int]:
    """Return {path_str: mtime_ns} for files under root, filtered for noise."""
    snap: dict[str, int] = {}
    for p in root.rglob("*"):
        if not p.is_file() or not _included(p):
            continue
        try:
            snap[str(p)] = p.stat().st_mtime_ns
        except FileNotFoundError:
            pass
    return snap


def start_child() -> subprocess.Popen:
    return subprocess.Popen(
        [str(BROWSE), "--foreground"],
        env=os.environ.copy(),
    )


def stop_child(child: subprocess.Popen, timeout: float = 5.0) -> None:
    if child.poll() is not None:
        return
    try:
        child.send_signal(signal.SIGTERM)
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
    except ProcessLookupError:
        pass


def diff_snaps(old: dict[str, int], new: dict[str, int]) -> str:
    changed = sum(1 for p, mt in new.items() if old.get(p) != mt and p in old)
    added = len(set(new) - set(old))
    removed = len(set(old) - set(new))
    parts = []
    if changed:
        parts.append(f"{changed} changed")
    if added:
        parts.append(f"{added} added")
    if removed:
        parts.append(f"{removed} removed")
    return ", ".join(parts) if parts else "metadata-only"


def main() -> int:
    if not BROWSE.exists():
        print(f"vidux dev: bin/vidux-browse not found at {BROWSE}", file=sys.stderr)
        return 1
    if not WATCH.exists():
        print(f"vidux dev: browser/ dir not found at {WATCH}", file=sys.stderr)
        return 1

    print(
        f"vidux dev: watching {WATCH} (poll every {POLL}s; ctrl-c to stop)",
        file=sys.stderr,
        flush=True,
    )
    child = start_child()
    last_snap = snapshot(WATCH)

    def shutdown(_signum, _frame):
        sys.stderr.write("\nvidux dev: shutting down\n")
        stop_child(child)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            time.sleep(POLL)
            if child.poll() is not None:
                print(
                    f"vidux dev: vidux-browse exited (status {child.returncode}), restarting",
                    file=sys.stderr,
                    flush=True,
                )
                child = start_child()
                last_snap = snapshot(WATCH)
                continue
            new_snap = snapshot(WATCH)
            if new_snap != last_snap:
                summary = diff_snaps(last_snap, new_snap)
                print(f"vidux dev: {summary} — restarting", file=sys.stderr, flush=True)
                stop_child(child)
                child = start_child()
                last_snap = new_snap
    except Exception as e:  # pragma: no cover — defensive
        print(f"vidux dev: error: {e}", file=sys.stderr)
        stop_child(child)
        return 1


if __name__ == "__main__":
    sys.exit(main())
