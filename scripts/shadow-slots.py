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
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Final

ROOT: Final = Path(os.environ.get("SHADOW_ROOT", Path(__file__).resolve().parent.parent)).resolve()
DOC: Final = ROOT / "docs" / "reference" / "slots.md"
KINDS: Final = ("pack", "skill")
LINE_RE: Final = re.compile(
    r"^- slot (?P<name>[a-z][a-z0-9-]{0,31}) \| kind: (?P<kind>[a-z]+) \| "
    r"default: (?P<default>[^|]+?) \| fills: (?P<fills>[^|]+?) \| absent: (?P<absent>.+)$"
)
SKILL_ROOTS: Final = (".claude/skills", ".agents/skills", ".cursor/skills")
PLUGIN_CACHE: Final = ".claude/plugins/cache"


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


def _resolve_pack(slot: dict[str, str], home: Path) -> tuple[str, str]:
    cache = home / PLUGIN_CACHE
    wanted = slot["default"]
    impostor: str | None = None
    if cache.is_dir():
        # Every candidate is read before answering: one stale or broken install
        # sorted first must not mask a good one under another version or
        # marketplace. A mismatch is only reported when no match exists at all.
        for manifest in sorted(cache.glob(f"*/{wanted}/*/.claude-plugin/plugin.json")):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("name") == wanted:
                return "pass", f"pack {data.get('version', '?')}"
            if impostor is None:
                impostor = f"{data.get('name')!r}"
    if impostor is not None:
        return "fail", f"a plugin at {wanted} answers to {impostor}, not {wanted!r}"
    return "warn", f"absent; {slot['absent']}"


def _resolve_skill(slot: dict[str, str], home: Path) -> tuple[str, str]:
    for root in SKILL_ROOTS:
        if (home / root / slot["default"] / "SKILL.md").is_file():
            return "pass", f"skill mounted in {root}"
    return "warn", f"absent; {slot['absent']}"


def _override(name: str) -> tuple[str, str, str] | None:
    """(variable, value, detail-suffix) for the strongest set env override.

    `SHADOW_SLOT_<NAME>` wins; `SHADOW_BUCKET_<NAME>` is honored as a
    deprecated fallback for exactly one release train (Branch B compat,
    2026-08-15), then dies.
    """
    suffix = name.upper().replace("-", "_")
    current = f"SHADOW_SLOT_{suffix}"
    value = os.environ.get(current)
    if value:
        return current, value, ""
    legacy = f"SHADOW_BUCKET_{suffix}"
    value = os.environ.get(legacy)
    if value:
        return legacy, value, " (deprecated env name; use SHADOW_SLOT_)"
    return None


def resolve(slot: dict[str, str], home: Path | None = None) -> tuple[str, str]:
    """(state, detail) for one slot. Never writes anything."""
    home = home or Path.home()
    override = _override(slot["name"])
    if override:
        variable, value, deprecated = override
        if value.strip().lower() == "off":
            return "pass", f"off by {variable} — the emptiness is deliberate{deprecated}"
        return ("pass", f"bound by {variable}{deprecated}") if Path(value).exists() else (
            "fail", f"{variable} points at nothing{deprecated}")
    return {"pack": _resolve_pack, "skill": _resolve_skill}[slot["kind"]](slot, home)


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
