#!/usr/bin/env python3
"""Read the one declaration-only Shadow configuration file in a repository.

``shadow.yaml`` lives at a Git repository root so it can travel with the
repository.  It is deliberately not stored under ``.shadow/``: that directory
holds local evidence and is commonly ignored.

This first reader has no routing or execution behavior.  It exposes a strict,
small YAML subset for later declaration readers and makes a malformed file
visible instead of silently falling back to defaults.  No file is the normal
case and returns an empty declaration.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Final


CONFIG_NAME: Final = "shadow.yaml"
KEY_RE: Final = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class ConfigError(ValueError):
    """A configuration error that can name its source line."""

    def __init__(self, line: int, detail: str) -> None:
        super().__init__(detail)
        self.line = line
        self.detail = detail


@dataclass(frozen=True)
class SourceLine:
    number: int
    indent: int
    text: str


@dataclass(frozen=True)
class LoadedConfig:
    repo: Path
    path: Path | None
    data: dict[str, Any]


def repository_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("--repo must name a Git worktree or a directory inside one")
    return Path(result.stdout.strip()).resolve()


def _lines(text: str) -> list[SourceLine]:
    """Tokenize the deliberately small YAML subset without guessing at YAML.

    Full-line comments and blank lines are allowed.  Inline comments, tabs,
    document markers, anchors, flow collections, and block scalars are not:
    accepting any of those half-way would be less honest than refusing them.
    """
    out: list[SourceLine] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        prefix = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in prefix:
            raise ConfigError(number, "tabs are not supported for indentation; use two spaces")
        if len(prefix) % 2:
            raise ConfigError(number, "indentation must use whole two-space levels")
        content = raw[len(prefix):]
        if content in {"---", "..."}:
            raise ConfigError(number, "multiple-document YAML is not supported")
        if re.search(r"\s#", content):
            raise ConfigError(number, "inline comments are not supported; put the comment on its own line")
        out.append(SourceLine(number, len(prefix), content))
    return out


def _mapping_entry(line: SourceLine) -> tuple[str, str]:
    if line.text.startswith("- ") or ":" not in line.text:
        raise ConfigError(line.number, "expected a mapping entry of the form 'key: value'")
    key, value = line.text.split(":", 1)
    if not KEY_RE.fullmatch(key):
        raise ConfigError(line.number, "keys must use letters, digits, hyphens, or underscores")
    if value and not value.startswith(" "):
        raise ConfigError(line.number, "put one space after ':' before a value")
    return key, value.strip()


def _looks_like_mapping(raw: str) -> bool:
    """Whether a list item uses this subset's ``key: value`` form.

    A colon alone is not enough: URLs and quoted strings are scalar list
    values, not malformed mappings.
    """
    if ":" not in raw:
        return False
    key, value = raw.split(":", 1)
    return bool(KEY_RE.fullmatch(key)) and (not value or value.startswith(" "))


def _scalar(raw: str, line: SourceLine) -> str:
    """Return a string only; this reader never silently coerces a value."""
    if not raw:
        raise ConfigError(line.number, "expected a value or an indented nested block")
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(line.number, f"invalid double-quoted string: {exc.msg}") from None
        if not isinstance(value, str):
            raise ConfigError(line.number, "quoted values must be strings")
        return value
    if raw.startswith("'"):
        raise ConfigError(line.number, "single-quoted strings are not supported; use double quotes")
    if raw.startswith(("[", "{", "|", ">", "&", "*", "!", "?")):
        raise ConfigError(line.number, "flow collections, block scalars, tags, anchors, and aliases are not supported")
    if any(char in raw for char in "[]{}"):
        raise ConfigError(line.number, "flow collections are not supported")
    if ": " in raw:
        raise ConfigError(line.number, "a scalar containing ': ' must be double-quoted")
    return raw


def _set(mapping: dict[str, Any], key: str, value: Any, line: SourceLine) -> None:
    if key in mapping:
        raise ConfigError(line.number, f"duplicate key {key!r}")
    mapping[key] = value


def _nested(lines: list[SourceLine], index: int, parent_indent: int) -> tuple[Any, int]:
    if index >= len(lines) or lines[index].indent <= parent_indent:
        line = lines[index - 1]
        raise ConfigError(line.number, "expected an indented nested block")
    expected = parent_indent + 2
    if lines[index].indent != expected:
        raise ConfigError(lines[index].number, "nested blocks must indent exactly two spaces")
    return _block(lines, index, expected)


def _mapping(lines: list[SourceLine], index: int, indent: int) -> tuple[dict[str, Any], int]:
    out: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ConfigError(line.number, "unexpected indentation")
        if line.text.startswith("- "):
            raise ConfigError(line.number, "cannot mix a list item into a mapping")
        key, raw = _mapping_entry(line)
        index += 1
        if raw:
            _set(out, key, _scalar(raw, line), line)
            if index < len(lines) and lines[index].indent > indent:
                raise ConfigError(lines[index].number, "a scalar cannot also have a nested block")
            continue
        value, index = _nested(lines, index, indent)
        _set(out, key, value, line)
    return out, index


def _list_mapping_item(
    lines: list[SourceLine], index: int, list_indent: int, first: SourceLine
) -> tuple[dict[str, Any], int]:
    """Parse ``- key: value`` plus any following mapping entries."""
    initial = SourceLine(first.number, list_indent + 2, first.text[2:])
    key, raw = _mapping_entry(initial)
    out: dict[str, Any] = {}
    index += 1

    if raw:
        _set(out, key, _scalar(raw, initial), initial)
    else:
        value, index = _nested(lines, index, initial.indent)
        _set(out, key, value, initial)

    entry_indent = list_indent + 2
    while index < len(lines) and lines[index].indent > list_indent:
        line = lines[index]
        if line.indent != entry_indent:
            raise ConfigError(line.number, "list mapping entries must indent exactly two spaces")
        if line.text.startswith("- "):
            raise ConfigError(line.number, "nested lists need a named mapping key")
        key, raw = _mapping_entry(line)
        index += 1
        if raw:
            _set(out, key, _scalar(raw, line), line)
            if index < len(lines) and lines[index].indent > entry_indent:
                raise ConfigError(lines[index].number, "a scalar cannot also have a nested block")
        else:
            value, index = _nested(lines, index, entry_indent)
            _set(out, key, value, line)
    return out, index


def _list(lines: list[SourceLine], index: int, indent: int) -> tuple[list[Any], int]:
    out: list[Any] = []
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ConfigError(line.number, "unexpected indentation")
        if not line.text.startswith("- "):
            raise ConfigError(line.number, "cannot mix a mapping entry into a list")
        raw = line.text[2:].strip()
        if not raw:
            index += 1
            value, index = _nested(lines, index, indent)
            out.append(value)
        elif _looks_like_mapping(raw):
            out_item, index = _list_mapping_item(lines, index, indent, line)
            out.append(out_item)
        else:
            out.append(_scalar(raw, line))
            index += 1
            if index < len(lines) and lines[index].indent > indent:
                raise ConfigError(lines[index].number, "a scalar list item cannot have a nested block")
    return out, index


def _block(lines: list[SourceLine], index: int, indent: int) -> tuple[Any, int]:
    if lines[index].text.startswith("- "):
        return _list(lines, index, indent)
    return _mapping(lines, index, indent)


def parse(text: str) -> dict[str, Any]:
    """Parse the accepted YAML subset and require a top-level mapping."""
    lines = _lines(text)
    if not lines:
        return {}
    if lines[0].indent:
        raise ConfigError(lines[0].number, "the document must begin at the left margin")
    data, index = _block(lines, 0, 0)
    if index != len(lines):
        raise ConfigError(lines[index].number, "unexpected content")
    if not isinstance(data, dict):
        raise ConfigError(lines[0].number, "the document must be a mapping")
    return data


def load(repo: Path) -> LoadedConfig:
    root = repository_root(repo)
    path = root / CONFIG_NAME
    if not path.exists() and not path.is_symlink():
        return LoadedConfig(repo=root, path=None, data={})
    if not path.is_file():
        raise ValueError(f"{CONFIG_NAME} is not a regular file")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        detail = getattr(exc, "strerror", None) or str(exc)
        raise ValueError(f"could not read {CONFIG_NAME}: {detail}") from exc
    return LoadedConfig(repo=root, path=path, data=parse(text))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        prog="shadow config",
        description="Read the declaration-only shadow.yaml at one Git repository root.",
    )
    value.add_argument("--repo", type=Path, default=Path.cwd(), help="repository or a directory inside it")
    value.add_argument("--json", action="store_true", help="print the parsed declaration as JSON")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        loaded = load(args.repo)
    except ConfigError as exc:
        print(f"shadow config: {CONFIG_NAME}:{exc.line}: {exc.detail}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"shadow config: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "schema": "shadow.config.v1",
            "path": CONFIG_NAME if loaded.path is not None else None,
            "config": loaded.data,
        }, indent=2, sort_keys=True))
    elif loaded.path is None:
        print(f"shadow config: no {CONFIG_NAME}; defaults remain unchanged")
    else:
        keys = len(loaded.data)
        suffix = "key" if keys == 1 else "keys"
        print(f"shadow config: read {CONFIG_NAME} ({keys} top-level {suffix})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
