#!/usr/bin/env python3
"""Explain the effective repo-local Shadow configuration without storing it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from shadow_config import ConfigError, find_config, load_config


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        rows: list[tuple[str, Any]] = []
        for key in sorted(value):
            name = f"{prefix}.{key}" if prefix else key
            child = value[key]
            if isinstance(child, dict) and child:
                rows.extend(_flatten(child, name))
            else:
                rows.append((name, child))
        return rows
    return [(prefix, value)]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="shadow config",
        description="Read one repo-root shadow.yaml and explain its effective values.",
    )
    result.add_argument("--explain", action="store_true", help="print effective values and their source")
    result.add_argument("--repo", type=Path, help="repository or child path; defaults to the current directory")
    result.add_argument("--json", action="store_true", help="emit the same explanation as JSON")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.explain:
        parser().error("--explain is required")
    start = (args.repo or Path.cwd()).resolve()
    try:
        source = find_config(start)
        config = load_config(start)
    except ConfigError as exc:
        print(f"shadow config: {exc}", file=sys.stderr)
        return 1

    source_name = source.name if source is not None else "built-in defaults"
    payload = {"source": source_name, "config": config}
    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 0

    print(f"source: {source_name}")
    for name, value in _flatten(config):
        rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
        print(f"{name} = {rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
