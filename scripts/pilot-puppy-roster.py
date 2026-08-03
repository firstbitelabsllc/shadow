#!/usr/bin/env python3
"""Create or display a safe, local Pilot Puppy role roster.

The roster is a trusted local configuration, not an evidence record.  It holds
only slot identifiers, work roles, and native host surfaces.  ``--file`` and
``PILOT_PUPPY_ROSTER_FILE`` are explicit local overrides; neither their paths
nor their contents are added to plans, browser status, or task receipts.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from pilot_puppy_roster_lib import (
    RosterError,
    RosterExistsError,
    initialize_roster,
    load_roster,
    roster_view,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="pilot-puppy roster",
        description="Create or display one provider-neutral, local role roster.",
    )
    commands = result.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("init", "create the default roster without overwriting"),
        ("show", "display the bounded local roster"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument(
            "--file",
            metavar="PATH",
            help="trusted explicit local roster override; never included in plans, browser status, or receipts",
        )
        command.add_argument("--json", action="store_true", help="print the bounded local roster projection")
    return result


def render(view: dict[str, Any]) -> str:
    roster = view["roster"]
    fingerprint = view["fingerprint"]
    lines = ["Pilot Puppy local roster", f"Revision: {roster['revision']}"]
    for slot in roster["slots"]:
        state = "enabled" if slot["enabled"] else "disabled"
        lines.append(f"- {slot['id']}: {slot['role']} via {slot['host']} (priority {slot['priority']}, {state})")
    lines.append(f"Fingerprint: {fingerprint['sha256']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            roster = initialize_roster(args.file)
            view = roster_view(roster)
            if args.json:
                print(json.dumps(view, indent=2, sort_keys=True))
            else:
                print("created local roster")
            return 0
        view = roster_view(load_roster(args.file))
        if args.json:
            print(json.dumps(view, indent=2, sort_keys=True))
        else:
            print(render(view), end="")
        return 0
    except RosterExistsError:
        print("pilot-puppy roster: local roster already exists; refusing to overwrite", file=sys.stderr)
        return 1
    except Exception:
        # Configuration errors must stay local and must never print an absolute
        # config path, parser traceback, or arbitrary malformed JSON content.
        print("pilot-puppy roster: unable to use local roster configuration", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
