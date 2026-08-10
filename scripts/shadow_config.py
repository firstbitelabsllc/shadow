#!/usr/bin/env python3
"""Read Shadow's optional repository-local declaration file."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import sys
from typing import Final


CONFIG_NAME: Final = "shadow.yaml"
MAX_CONFIG_BYTES: Final = 64 * 1024
SCHEMA: Final = "shadow.config.explain.v1"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    source: str
    version: int = 1

    def explain(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "source": self.source,
            "version": self.version,
            "bindings": {},
        }


def repository_root(start: Path) -> Path:
    try:
        current = start.resolve(strict=True)
    except OSError as error:
        raise ConfigError("repository path is unavailable") from error
    if not current.is_dir():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise ConfigError("no Git repository found from --repo or the current directory")


def _read_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise ConfigError(f"{CONFIG_NAME}: could not be read safely") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ConfigError(f"{CONFIG_NAME}: must be a regular, non-symlink file")
        chunks: list[bytes] = []
        remaining = MAX_CONFIG_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
    finally:
        os.close(descriptor)
    if len(content) > MAX_CONFIG_BYTES:
        raise ConfigError(f"{CONFIG_NAME}: exceeds the 64 KiB declaration limit")
    return content


def load(start: Path) -> Config:
    path = repository_root(start) / CONFIG_NAME
    try:
        content = _read_regular_file(path)
    except FileNotFoundError:
        return Config(source="built-in")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError(f"{CONFIG_NAME}: is not valid UTF-8") from error

    version_line: int | None = None
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        value = line.split("#", 1)[0].rstrip()
        if value == "version: 1":
            if version_line is not None:
                raise ConfigError(f"{CONFIG_NAME}:{line_number}: duplicate version")
            version_line = line_number
            continue
        raise ConfigError(f"{CONFIG_NAME}:{line_number}: unsupported declaration")
    if version_line is None:
        raise ConfigError(f"{CONFIG_NAME}:1: expected 'version: 1'")
    return Config(source=CONFIG_NAME)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow config",
        description="Explain the optional repository-local Shadow declaration.",
    )
    parser.add_argument("--repo", default=".", help="repository path (default: cwd)")
    parser.add_argument("--explain", action="store_true", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = load(Path(args.repo)).explain()
    except ConfigError as error:
        print(f"shadow config: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"shadow config: {report['source']} (version {report['version']})")
        print("bindings: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
