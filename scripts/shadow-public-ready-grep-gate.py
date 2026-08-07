#!/usr/bin/env python3
"""Fail closed on private or secret-shaped material in the public tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
MAX_TEXT_BYTES = 1_000_000
FORBIDDEN_SUFFIXES = {".key", ".log", ".pem", ".p12", ".token", ".jsonl"}
FORBIDDEN_NAMES = {".env", ".env.local", ".npmrc"}
PRIVATE_HOME = re.compile(r"(?:/Users/|/home/)([A-Za-z0-9._-]+)(?:/|\b)")
WINDOWS_HOME = re.compile(r"[A-Za-z]:\\Users\\([A-Za-z0-9._-]+)(?:\\|\b)")
FILE_PATH = re.compile(r"file:///([A-Za-z0-9._-]+)")
OLD_BRAND = re.compile(r"(?i)pilot[-_ ]?puppy")
PLACEHOLDER_USERS = {"example", "name", "person", "private", "user", "username"}
SECRET = re.compile(
    r"(?:sk-(?:ant-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)


def git_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "git ls-files failed")
    return [root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def working_paths(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "node_modules" not in path.parts
        and "test-results" not in path.parts
        and "playwright-report" not in path.parts
    )


def text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > MAX_TEXT_BYTES or b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def contains_private_path(value: str) -> bool:
    if FILE_PATH.search(value):
        return True
    matches = [*PRIVATE_HOME.finditer(value), *WINDOWS_HOME.finditer(value)]
    return any(match.group(1).lower() not in PLACEHOLDER_USERS for match in matches)


def metadata_errors(root: Path) -> list[str]:
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        version = (root / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, json.JSONDecodeError, IndexError) as exc:
        return [f"metadata unreadable: {exc}"]
    errors = []
    if package.get("name") != "@firstbitelabs/shadow":
        errors.append("package name must be @firstbitelabs/shadow")
    if package.get("private") is not False:
        errors.append("package must be public")
    if package.get("version") != version or plugin.get("version") != version:
        errors.append("package, plugin, and VERSION must match")
    expected = "https://github.com/firstbitelabsllc/shadow"
    if expected not in str(package.get("homepage", "")):
        errors.append("homepage must use the canonical public repository")
    if plugin.get("name") != "shadow":
        errors.append("plugin name must be shadow")
    return errors


def scan(root: Path, paths: list[Path], *, metadata: bool) -> dict:
    findings = []
    for path in paths:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if not path.exists() or path.is_symlink():
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append({"file": relative, "line": 0, "reason": "forbidden release file"})
            continue
        content = text(path)
        if content is None:
            continue
        # PLAN.md and CHANGELOG.md keep pre-rename history as receipts; the
        # read-compat code and its tests name the legacy marker deliberately.
        brand_exempt = relative in {"PLAN.md", "CHANGELOG.md", "docs/guide/installation.md"} or "pilot-puppy" in relative or relative.startswith(("scripts/", "tests/"))
        for number, line in enumerate(content.splitlines(), 1):
            if contains_private_path(line):
                findings.append({"file": relative, "line": number, "reason": "private filesystem path"})
            if SECRET.search(line):
                findings.append({"file": relative, "line": number, "reason": "secret-shaped value"})
            if not brand_exempt and OLD_BRAND.search(line):
                findings.append({"file": relative, "line": number, "reason": "old product name"})
    errors = metadata_errors(root) if metadata else []
    return {
        "schema": "shadow.public-ready.v1",
        "ok": not findings and not errors,
        "scanned_files": len(paths),
        "findings": findings,
        "errors": errors,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", type=Path, default=ROOT)
    result.add_argument("--tracked-only", action="store_true")
    result.add_argument("--metadata", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    try:
        report = scan(root, git_paths(root) if args.tracked_only else working_paths(root), metadata=args.metadata)
    except (OSError, RuntimeError) as exc:
        report = {"schema": "shadow.public-ready.v1", "ok": False, "scanned_files": 0, "findings": [], "errors": [str(exc)]}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
