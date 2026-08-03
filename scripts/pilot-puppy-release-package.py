#!/usr/bin/env python3
"""Verify one small, public, installable Pilot Puppy npm artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
MAX_FILE_COUNT = 100
MAX_UNPACKED_BYTES = 2_000_000
REQUIRED_FILES = {
    ".claude-plugin/plugin.json",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "SKILL.md",
    "VERSION",
    "bin/pilot-puppy",
    "bin/pilot-puppy-browse",
    "browser/chief_of_staff.py",
    "browser/decision_mode.py",
    "browser/outcome_source.py",
    "browser/server.py",
    "browser/static/app.js",
    "browser/static/index.html",
    "browser/static/style.css",
    "docs/reference/chief-of-staff.md",
    "docs/reference/native-hosts.md",
    "docs/reference/outcome-choice.md",
    "docs/reference/roster.md",
    "docs/reference/routing.md",
    "examples/outcome-choice/example.json",
    "package.json",
    "schemas/chief-of-staff.v1.json",
    "schemas/decision-choice.v1.json",
    "schemas/decision-receipt.v1.json",
    "schemas/outcome-choice.v1.json",
    "schemas/route.v1.json",
    "schemas/roster.v1.json",
    "scripts/pilot-puppy-checkpoint.py",
    "scripts/pilot-puppy-doctor.py",
    "scripts/pilot-puppy-host.py",
    "scripts/pilot-puppy-init.py",
    "scripts/pilot-puppy-outcome-validate.py",
    "scripts/pilot-puppy-public-ready-grep-gate.py",
    "scripts/pilot-puppy-release-package.py",
    "scripts/pilot-puppy-roster.py",
    "scripts/pilot-puppy-seat.py",
    "scripts/pilot-puppy-route.py",
    "scripts/pilot-puppy-status.py",
    "scripts/pilot_puppy_roster_lib.py",
    "scripts/pilot_puppy_seat_lib.py",
    "scripts/pilot_puppy_route_lib.py",
    "scripts/pilot_puppy_task_lib.py",
}
FORBIDDEN_ROOTS = {
    ".git",
    ".github",
    "node_modules",
    "tests",
    "test-results",
    "playwright-report",
}
FORBIDDEN_FILES = {"PLAN.md", "package-lock.json", ".gitleaks.toml", "playwright.config.ts", "vitest.config.mjs"}
FORBIDDEN_SUFFIXES = {".jsonl", ".key", ".log", ".pem", ".p12", ".token"}


def normalize(value: str) -> str:
    return PurePosixPath(value.replace("\\", "/").removeprefix("package/")).as_posix()


def source_version(root: Path) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()


def forbidden(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        not pure.parts
        or pure.parts[0] in FORBIDDEN_ROOTS
        or path in FORBIDDEN_FILES
        or "__pycache__" in pure.parts
        or any(part.startswith(".env") for part in pure.parts)
        or pure.suffix.lower() in FORBIDDEN_SUFFIXES
    )


def validate_release_candidate(
    package: dict[str, Any],
    plugin: dict[str, Any],
    pack: dict[str, Any],
    *,
    version: str,
    tracked_paths: Iterable[str],
    dirty_paths: Iterable[str] = (),
    allow_dirty: bool = False,
    expected_version: str | None = None,
) -> list[str]:
    errors = []
    files = {normalize(str(item["path"])) for item in pack.get("files", []) if item.get("path")}
    tracked = {normalize(path) for path in tracked_paths}
    dirty = sorted(files & {normalize(path) for path in dirty_paths})
    wanted_version = expected_version or version
    expected_repo = "https://github.com/firstbitelabsllc/pilot-puppy"
    if expected_version and version != expected_version:
        errors.append("VERSION does not match --expect-version")
    if package.get("name") != "pilot-puppy" or plugin.get("name") != "pilot-puppy":
        errors.append("package and plugin names must be pilot-puppy")
    if package.get("private") is not False:
        errors.append("package must be public")
    if package.get("version") != wanted_version or plugin.get("version") != wanted_version or pack.get("version") != wanted_version:
        errors.append("package, plugin, packed artifact, and VERSION must match")
    if package.get("bin") != {"pilot-puppy": "bin/pilot-puppy"}:
        errors.append("package must expose only the pilot-puppy command")
    if expected_repo not in str(package.get("homepage", "")) or expected_repo not in str(package.get("repository", {}).get("url", "")):
        errors.append("package must point at the canonical public repository")
    publish = package.get("publishConfig", {})
    if publish.get("access") != "public" or publish.get("provenance") is not True:
        errors.append("publishing must be public with provenance")
    missing = sorted(REQUIRED_FILES - files)
    if missing:
        errors.append("packed artifact is missing: " + ", ".join(missing))
    blocked = sorted(path for path in files if forbidden(path))
    if blocked:
        errors.append("packed artifact contains forbidden files: " + ", ".join(blocked))
    skills = sorted(path for path in files if PurePosixPath(path).name == "SKILL.md")
    if skills != ["SKILL.md"]:
        errors.append("packed artifact must contain exactly the root SKILL.md")
    untracked = sorted(files - tracked)
    if untracked and not allow_dirty:
        errors.append("packed artifact contains untracked files: " + ", ".join(untracked))
    if dirty and not allow_dirty:
        errors.append("packed artifact contains uncommitted bytes: " + ", ".join(dirty))
    if len(files) > MAX_FILE_COUNT:
        errors.append(f"packed artifact exceeds {MAX_FILE_COUNT} files")
    if int(pack.get("unpackedSize", 0) or 0) > MAX_UNPACKED_BYTES:
        errors.append(f"packed artifact exceeds {MAX_UNPACKED_BYTES} unpacked bytes")
    return errors


def command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return result


def tracked_files(root: Path) -> set[str]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("git ls-files failed")
    return {item.decode("utf-8") for item in result.stdout.split(b"\0") if item}


def dirty_files(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("git status failed")
    paths = set()
    rows = [row for row in result.stdout.split(b"\0") if row]
    index = 0
    while index < len(rows):
        row = rows[index].decode("utf-8", errors="surrogateescape")
        paths.add(row[3:])
        if row[:2] in {"R ", "C ", "RM", "CM"} and index + 1 < len(rows):
            index += 1
            paths.add(rows[index].decode("utf-8", errors="surrogateescape"))
        index += 1
    return paths


def pack(root: Path, destination: Path) -> tuple[dict[str, Any], Path, str]:
    rows = json.loads(
        command(
            ["npm", "pack", "--json", "--ignore-scripts", "--pack-destination", str(destination)],
            root,
        ).stdout
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("npm pack returned an unexpected manifest")
    tarball = destination / rows[0]["filename"]
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    return rows[0], tarball, digest


def stranger_install(tarball: Path, root: Path, expected_version: str) -> None:
    consumer = root / "consumer"
    consumer.mkdir()
    (consumer / "package.json").write_text('{"private":true}\n', encoding="utf-8")
    command(["npm", "install", "--ignore-scripts", "--no-fund", "--audit", str(tarball)], consumer)
    cli = consumer / "node_modules" / ".bin" / "pilot-puppy"
    version = command([str(cli), "--version"], consumer).stdout.strip()
    if version != expected_version:
        raise RuntimeError("installed command version does not match source")
    command([str(cli), "help"], consumer)


def verify(root: Path, *, expected_version: str | None = None, allow_dirty: bool = False) -> dict[str, Any]:
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    version = source_version(root)
    with tempfile.TemporaryDirectory(prefix="pilot-puppy-release-") as dirname:
        temp = Path(dirname)
        first = temp / "first"
        second = temp / "second"
        first.mkdir()
        second.mkdir()
        manifest, tarball, first_sha = pack(root, first)
        second_manifest, _, second_sha = pack(root, second)
        errors = validate_release_candidate(
            package,
            plugin,
            manifest,
            version=version,
            tracked_paths=tracked_files(root),
            dirty_paths=dirty_files(root),
            allow_dirty=allow_dirty,
            expected_version=expected_version,
        )
        if first_sha != second_sha or manifest.get("files") != second_manifest.get("files"):
            errors.append("repeated npm pack runs are not reproducible")
        install_ok = False
        if not errors:
            stranger_install(tarball, temp, version)
            install_ok = True
    dirty = sorted(dirty_files(root))
    return {
        "schema": "pilot-puppy.release.v1",
        "ok": not errors,
        "publishable": not errors and not dirty and not allow_dirty,
        "version": version,
        "file_count": len(manifest.get("files", [])),
        "unpacked_bytes": int(manifest.get("unpackedSize", 0) or 0),
        "sha256": first_sha,
        "reproducible": first_sha == second_sha,
        "stranger_install": install_ok,
        "dirty_files": dirty,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--expect-version")
    parser.add_argument("--allow-dirty", action="store_true", help="allow a non-publishable development receipt")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = verify(args.root.resolve(), expected_version=args.expect_version, allow_dirty=args.allow_dirty)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        report = {"schema": "pilot-puppy.release.v1", "ok": False, "publishable": False, "errors": [str(exc)]}
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["ok"]:
        print(f"pilot-puppy release package: OK ({report['version']}, {report['file_count']} files, sha256={report['sha256']})")
    else:
        print("pilot-puppy release package: FAILED", file=sys.stderr)
        for error in report["errors"]:
            print(f"- {error}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
