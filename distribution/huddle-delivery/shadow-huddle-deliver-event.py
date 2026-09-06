#!/usr/bin/env python3
"""Confined event runner: attempt bounded delivery for one Huddle event.

Runs under the seatbelt with read-only descriptors: the entrypoint code, the
capability descriptor, the contacts directory (bounded enumeration; the
kernel admits only the parent-selected contact files), and the runner-fixed
board pathname. It re-reads the board atomically, pins the exact huddle
generation, re-derives eligibility exactly as the parent did, and attempts
one bounded envelope per current, eligible, armed contact. Output is the
closed attempted-receipt list; any refusal exits non-zero with no output.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import sys
import time

sys.path.insert(0, os.environ["SHADOW_HUDDLE_SCRIPTS_PATH"])

import shadow_contacts as contacts
import shadow_delivery as delivery
import shadow_huddle_event as core

BUDGET_SECONDS = 1.5


def main() -> int:
    if not (sys.flags.isolated and sys.flags.dont_write_bytecode):
        raise SystemExit("delivery requires the isolated interpreter")
    deadline = time.monotonic() + BUDGET_SECONDS
    event = json.load(sys.stdin)
    core.validate_event(event)
    board = core._read_board(Path(os.environ["SHADOW_HUDDLE_BOARD_PATH"]),
                             component_walk=False)
    huddle = next((h for h in board.get("huddles", [])
                   if h.get("id") == event["huddle_id"]
                   and h.get("generation") == event["generation"]), None)
    if huddle is None:
        raise SystemExit("current huddle generation unavailable")
    current = core._current_claims(board)
    entries = delivery.read_armed_entries(
        os.read(int(os.environ["SHADOW_HUDDLE_CAPABILITIES_FD"]), 16 * 1024 + 1),
        json.loads(os.environ["SHADOW_HUDDLE_ALLOWED_TARGET_DIGESTS"]),
        now=datetime.now(timezone.utc))
    receipts = delivery.deliver(
        event=event, huddle=huddle, current_claims=current,
        capability_entries=entries,
        contacts_dir_fd=int(os.environ["SHADOW_HUDDLE_CONTACTS_DIR_FD"]),
        now=datetime.now(timezone.utc),
        deadline_seconds=deadline - time.monotonic())
    sys.stdout.write(json.dumps(receipts, sort_keys=True,
                                separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (contacts.ContactRefused, OSError, ValueError,
            KeyError, StopIteration, json.JSONDecodeError) as exc:
        sys.stderr.write(f"event delivery refused: {exc}\n")
        raise SystemExit(1)
