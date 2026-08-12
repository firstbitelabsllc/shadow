#!/usr/bin/env python3
"""Resolve the extension buckets declared in docs/reference/buckets.md.

A bucket is a named capability the method assumes it can reach. This reads the
declaration and answers, per bucket, one of: present, absent, stale, off.

Three rules keep it from becoming the thing Boundaries ban:

1. **Zero resolved state is written.** Every answer is derived at read time,
   the same law as milestone status. A file that stamps nothing cannot drift.
2. **Absent never fails.** A machine that has not installed an optional
   capability is not a broken install — and `shadow doctor` under a scratch
   HOME must still exit 0.
3. **`kind:` is the check.** Two kinds, two fixed resolution algorithms in
   code, exactly as a `proof:`'s class determines its machinery. A prose
   predicate here would be a doc that drifts from what runs.

Every check asks only whether a capability Shadow reaches for is reachable. No
bucket asserts anything about tooling Shadow does not use: which recall,
memory, or model tooling a person runs is their own configuration, and a check
that failed over it would be Shadow policing a machine it does not own.
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
DOC: Final = ROOT / "docs" / "reference" / "buckets.md"
KINDS: Final = ("pack", "skill")
LINE_RE: Final = re.compile(
    r"^- bucket (?P<name>[a-z][a-z0-9-]{0,31}) \| kind: (?P<kind>[a-z]+) \| "
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


def _resolve_pack(bucket: dict[str, str], home: Path) -> tuple[str, str]:
    cache = home / PLUGIN_CACHE
    wanted = bucket["default"]
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
    return "warn", f"absent; {bucket['absent']}"


def _resolve_skill(bucket: dict[str, str], home: Path) -> tuple[str, str]:
    for root in SKILL_ROOTS:
        if (home / root / bucket["default"] / "SKILL.md").is_file():
            return "pass", f"skill mounted in {root}"
    return "warn", f"absent; {bucket['absent']}"


def resolve(bucket: dict[str, str], home: Path | None = None) -> tuple[str, str]:
    """(state, detail) for one bucket. Never writes anything."""
    home = home or Path.home()
    override = os.environ.get(f"SHADOW_BUCKET_{bucket['name'].upper().replace('-', '_')}")
    if override:
        variable = f"SHADOW_BUCKET_{bucket['name'].upper().replace('-', '_')}"
        if override.strip().lower() == "off":
            return "pass", f"off by {variable} — the emptiness is deliberate"
        return ("pass", f"bound by {variable}") if Path(override).exists() else (
            "fail", f"{variable} points at nothing")
    return {"pack": _resolve_pack, "skill": _resolve_skill}[bucket["kind"]](bucket, home)


def checks(home: Path | None = None) -> list[dict[str, Any]]:
    results = []
    for bucket in declared():
        state, detail = resolve(bucket, home)
        results.append({"name": f"bucket: {bucket['name']}", "state": state, "detail": detail})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow buckets",
        description="Report which extension buckets are filled on this machine.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = checks()
    if not results:
        print("shadow buckets: no buckets declared in docs/reference/buckets.md", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"schema": "shadow.buckets.v1", "checks": results}, indent=2))
    else:
        for check in results:
            print(f"[{check['state'].upper():4}] {check['name']}: {check['detail']}")
    # Absent never fails; only a wrong or violated binding does.
    return 1 if any(c["state"] == "fail" for c in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
