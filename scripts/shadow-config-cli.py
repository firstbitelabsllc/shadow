#!/usr/bin/env python3
"""Initialize or explain the effective machine-local Shadow configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from shadow_config import (
    ConfigError,
    config_paths,
    find_config,
    initialize_local_config,
    load_config,
)


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
        description="Initialize or explain one ignored repository-local override.",
    )
    action = result.add_mutually_exclusive_group(required=True)
    action.add_argument("--explain", action="store_true", help="print effective values and their source")
    action.add_argument(
        "--init-local",
        action="store_true",
        help="copy the reviewed template to the ignored effective config",
    )
    result.add_argument("--repo", type=Path, help="repository or child path; defaults to the current directory")
    result.add_argument("--json", action="store_true", help="emit the same explanation as JSON")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    start = (args.repo or Path.cwd()).resolve()
    if args.init_local:
        try:
            config, template, created = initialize_local_config(start)
        except ConfigError as exc:
            print(f"shadow config: {exc}", file=sys.stderr)
            return 1
        payload = {
            "created": created,
            "effective": config.relative_to(config_paths(start)[0]).as_posix(),
            "template": (
                template.relative_to(config_paths(start)[0]).as_posix()
                if template.is_relative_to(config_paths(start)[0])
                else template.name
            ),
            "tracked": False,
        }
        if args.json:
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        else:
            state = "created" if created else "already exists"
            print(f"effective: {payload['effective']} ({state}, locally ignored, not staged)")
            print(f"template: {payload['template']} (recommended only)")
        return 0

    try:
        source = find_config(start)
        config = load_config(start)
    except ConfigError as exc:
        print(f"shadow config: {exc}", file=sys.stderr)
        return 1

    root, effective, template = config_paths(start)
    source_name = effective.relative_to(root).as_posix() if source is not None else "built-in defaults"
    payload = {
        "source": source_name,
        "effective": effective.relative_to(root).as_posix(),
        "template": template.relative_to(root).as_posix(),
        "config": config,
    }
    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 0

    print(f"source: {source_name}")
    print(f"effective: {payload['effective']} (machine-local, must be ignored)")
    print(f"template: {payload['template']} (recommended only)")
    for name, value in _flatten(config):
        rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
        print(f"{name} = {rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
