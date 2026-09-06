#!/usr/bin/env python3
"""Confined registration runner: store one closed expiring contact.

Runs under the seatbelt with exactly three descriptors: the entrypoint code
(read-only), the capability descriptor (read-only), and the contacts
directory (the only writable descriptor). It validates the request
structurally, confirms the (provider, capability) pair is armed exactly
once, stores the contact under its canonical nonce with the ten-minute
lease, and prints the closed registration receipt. Any refusal exits
non-zero with no receipt; the parent then reports the runner as unavailable.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sys

sys.path.insert(0, os.environ["SHADOW_HUDDLE_SCRIPTS_PATH"])

import shadow_board_schema as board_schema
import shadow_contacts as contacts
import shadow_delivery as delivery


def _valid_seat(seat):
    try:
        board_schema.validate_owner(seat)
        return True
    except Exception:
        return False


def main() -> int:
    if not (sys.flags.isolated and sys.flags.dont_write_bytecode):
        raise SystemExit("registration requires the isolated interpreter")
    argv = sys.argv[1:]
    seat = argv[1] if len(argv) == 2 and argv[0] == "--seat" else None
    if seat is None or not _valid_seat(seat):
        raise SystemExit("registration seat is invalid")
    request = contacts.parse_registration(sys.stdin.buffer.read(16 * 1024 + 1))
    raw_capabilities = os.read(int(os.environ["SHADOW_HUDDLE_CAPABILITIES_FD"]), 16 * 1024 + 1)
    entries = delivery.read_armed_entries(
        raw_capabilities, json.loads(os.environ["SHADOW_HUDDLE_ALLOWED_TARGET_DIGESTS"]),
        now=datetime.now(timezone.utc))
    contacts.capability_pair(request["provider"], request["capability"], entries)
    contacts.validate_registration(request, seat=seat)
    now = datetime.now(timezone.utc)
    stored = contacts.stored_registration(request, seat=seat, now=now)
    contacts.write_contact(int(os.environ["SHADOW_HUDDLE_CONTACTS_DIR_FD"]),
                           stored, now=now)
    receipt = {"registered": True, "provider": stored["provider"],
               "capability": stored["capability"],
               "instance_nonce": stored["instance_nonce"]}
    sys.stdout.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (contacts.ContactRefused, OSError, ValueError, KeyError) as exc:
        sys.stderr.write(f"contact registration refused: {exc}\n")
        raise SystemExit(1)
