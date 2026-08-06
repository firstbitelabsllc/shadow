#!/usr/bin/env python3
"""Configure one owner-local native selector for an already-declared roster slot.

This command is deliberately local setup only.  It does not inspect providers,
accounts, billing, quota, credentials, model availability, or projects.  Use
``shadow host run --use-seat`` only with an already-written sealed route.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from shadow_seat_lib import (
    SeatExistsError,
    initialize_seat_overlay,
    load_seat_overlay,
    seat_view,
    set_seat_selector,
)
from shadow_roster_lib import load_roster


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="shadow seat",
        description="Configure an owner-local selector for one declared native roster slot.",
    )
    commands = root.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="create an empty private seat overlay without overwriting")
    initialize.add_argument("--file", metavar="PATH", help="trusted explicit local seat-overlay override")
    initialize.add_argument("--json", action="store_true", help="print the owner-local overlay view")
    show = commands.add_parser("show", help="display the explicit private seat overlay")
    show.add_argument("--file", metavar="PATH", help="trusted explicit local seat-overlay override")
    show.add_argument("--roster-file", metavar="PATH", help="trusted local generic roster override")
    show.add_argument("--json", action="store_true", help="print the owner-local overlay view")
    set_command = commands.add_parser("set", help="bind one existing native slot to one local selector")
    set_command.add_argument("--slot", required=True, help="existing enabled native roster slot identifier")
    selector = set_command.add_mutually_exclusive_group(required=True)
    selector.add_argument("--model", metavar="MODEL", help="safe native model selector")
    selector.add_argument("--profile", metavar="PROFILE", help="safe Codex profile selector")
    set_command.add_argument("--file", metavar="PATH", help="trusted explicit local seat-overlay override")
    set_command.add_argument("--roster-file", metavar="PATH", help="trusted local generic roster override")
    set_command.add_argument("--json", action="store_true", help="print the owner-local overlay view")
    return root


def render(view: dict[str, Any]) -> str:
    overlay = view["overlay"]
    lines = ["Shadow private seats", f"Revision: {overlay['revision']}"]
    if not overlay["seats"]:
        lines.append("- no native selectors configured")
    for seat in overlay["seats"]:
        lines.append(f"- {seat['slot']} via {seat['host']}: {seat['selector']['kind']}={seat['selector']['value']}")
    return "\n".join(lines) + "\n"


def view(file: str | None, roster_file: str | None) -> dict[str, Any]:
    return seat_view(load_seat_overlay(file), load_roster(roster_file))


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            overlay = initialize_seat_overlay(args.file)
            result = seat_view(overlay)
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print("created private seat overlay")
            return 0
        if args.command == "set":
            kind, value = ("model", args.model) if args.model is not None else ("profile", args.profile)
            overlay = set_seat_selector(
                args.slot,
                kind,
                value,
                overlay_path=args.file,
                roster_path=args.roster_file,
            )
            result = seat_view(overlay, load_roster(args.roster_file))
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print("private seat selector is ready")
            return 0
        result = view(args.file, args.roster_file)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(render(result), end="")
        return 0
    except SeatExistsError:
        print("shadow seat: private seat overlay already exists; refusing to overwrite", file=sys.stderr)
        return 1
    except Exception:
        # Explicit local selector values and locations never belong in an error,
        # route packet, browser/status projection, or project receipt.
        print("shadow seat: unable to use private seat configuration", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
