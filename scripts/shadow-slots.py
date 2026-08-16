#!/usr/bin/env python3
"""Resolve the extension slots declared in docs/reference/slots.md.

A slot is a named capability the method assumes it can reach. This reads the
declaration and answers, per slot, one of: present, absent, stale, off.

Three rules keep it from becoming the thing Boundaries ban:

1. **Zero resolved state is written.** Every answer is derived at read time,
   the same law as milestone status. A file that stamps nothing cannot drift.
2. **Absent never fails.** A machine that has not installed an optional
   capability is not a broken install — and `shadow doctor` under a scratch
   HOME must still exit 0.
3. **`kind:` is the check.** Two kinds, two fixed resolution algorithms in
   code, exactly as a `proof:`'s class determines its machinery. A prose
   predicate here would be a doc that drifts from what runs.

A slot names only a capability Shadow itself reaches for. It never asserts
anything about the rest of a machine: which memory backend or model tooling a
person runs is their own configuration, and a check that failed over it would
be Shadow policing software it does not use. The memory slot reaches only for
the routing file it names — never the backend behind it.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
from typing import Any, Final

ROOT: Final = Path(os.environ.get("SHADOW_ROOT", Path(__file__).resolve().parent.parent)).resolve()
DOC: Final = ROOT / "docs" / "reference" / "slots.md"
KINDS: Final = ("skill",)
LINE_RE: Final = re.compile(
    r"^- slot (?P<name>[a-z][a-z0-9-]{0,31}) \| kind: (?P<kind>[a-z]+) \| "
    r"default: (?P<default>[^|]+?) \| fills: (?P<fills>[^|]+?) \| absent: (?P<absent>.+)$"
)
SKILL_ROOTS: Final = (".claude/skills", ".agents/skills", ".cursor/skills")


def declared(doc: Path | None = None) -> list[dict[str, str]]:
    try:
        text = (doc or DOC).read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        match = LINE_RE.match(line)
        if match:
            found = {k: v.strip() for k, v in match.groupdict().items()}
            if found["kind"] in KINDS:
                out.append(found)
    return out


def _resolve_skill(slot: dict[str, str], home: Path) -> tuple[str, str]:
    for root in SKILL_ROOTS:
        if (home / root / slot["default"] / "SKILL.md").is_file():
            return "pass", f"skill mounted in {root}"
    return "warn", f"absent; {slot['absent']}"


def _override(name: str) -> tuple[str, str] | None:
    """(variable, value) for a set SHADOW_SLOT_<NAME> override."""
    current = f"SHADOW_SLOT_{name.upper().replace('-', '_')}"
    value = os.environ.get(current)
    if value:
        return current, value
    return None


def resolve(slot: dict[str, str], home: Path | None = None) -> tuple[str, str]:
    """(state, detail) for one slot. Never writes anything."""
    home = home or Path.home()
    override = _override(slot["name"])
    if override:
        variable, value = override
        if value.strip().lower() == "off":
            return "pass", f"off by {variable} — the emptiness is deliberate"
        return ("pass", f"bound by {variable}") if Path(value).exists() else (
            "fail", f"{variable} points at nothing")
    return {"skill": _resolve_skill}[slot["kind"]](slot, home)


def checks(home: Path | None = None) -> list[dict[str, Any]]:
    results = []
    for slot in declared():
        state, detail = resolve(slot, home)
        results.append({"name": f"slot: {slot['name']}", "state": state, "detail": detail})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow slots",
        description="Report which extension slots are filled on this machine.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = checks()
    if not results:
        print("shadow slots: no slots declared in docs/reference/slots.md", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"schema": "shadow.slots.v1", "checks": results}, indent=2))
    else:
        for check in results:
            print(f"[{check['state'].upper():4}] {check['name']}: {check['detail']}")
    # Absent never fails; only a wrong or violated binding does.
    return 1 if any(c["state"] == "fail" for c in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
