#!/usr/bin/env python3
"""Fail closed when the npm release candidate is incomplete or over-broad."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
MAX_FILE_COUNT = 320
MAX_UNPACKED_BYTES = 4_000_000

REQUIRED_FILES = {
    ".claude-plugin/plugin.json",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "SKILL.md",
    "VERSION",
    "benchmarks/v2/FIXTURE-RELEASE.md",
    "benchmarks/v2/PROTOCOL.md",
    "benchmarks/v2/STATUS.json",
    "benchmarks/v2/STATUS.md",
    "benchmarks/v2/manifest.json",
    "benchmarks/v3/PROTOCOL.md",
    "benchmarks/v3/STATUS.json",
    "benchmarks/v3/manifest.json",
    "bin/vidux",
    "bin/vidux-browse",
    "browser/safe_files.py",
    "browser/server.py",
    "browser/static/app.js",
    "browser/static/index.html",
    "browser/static/style.css",
    "browser/static/work-queue.js",
    "commands/vidux.md",
    "package.json",
    "scripts/vidux-build.sh",
    "scripts/vidux-benchmark-v2.py",
    "scripts/vidux-benchmark-v3.py",
    "scripts/vidux-completion.sh",
    "scripts/vidux-config.py",
    "scripts/vidux-doctor-cli.sh",
    "scripts/vidux-drift-log.py",
    "scripts/vidux-http-smoke.py",
    "scripts/vidux-init.sh",
    "scripts/vidux-release-package.py",
    "scripts/vidux-release.sh",
    "scripts/vidux-status.py",
}

FORBIDDEN_ROOTS = {
    ".git",
    ".github",
    ".opencode",
    "evaluations",
    "evidence",
    "investigations",
    "node_modules",
    "projects",
    "prompts",
    "tests",
    "test-results",
    "playwright-report",
    "blob-report",
}
FORBIDDEN_FILES = {
    ".gitleaks.toml",
    ".gitleaksignore",
    "AGENTS.md",
    "ASK-LEO.md",
    "PLAN.md",
    "impeccable-vidux.md",
    "package-lock.json",
    "playwright.config.ts",
    "vitest.config.mjs",
}
FORBIDDEN_SUFFIXES = {".jsonl", ".key", ".log", ".pem", ".pyc", ".pyo", ".token"}
V3_ALLOWED_FILES = {
    "benchmarks/v3/PROTOCOL.md",
    "benchmarks/v3/STATUS.json",
    "benchmarks/v3/manifest.json",
}


def source_version(root: Path) -> str:
    for raw_line in (root / "VERSION").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            return line
    raise ValueError("VERSION has no non-comment version line")


def normalize_pack_path(raw_path: str) -> str:
    path = raw_path.replace("\\", "/").removeprefix("package/")
    return PurePosixPath(path).as_posix()


def is_forbidden(path: str) -> bool:
    pure = PurePosixPath(path)
    if not pure.parts:
        return True
    if pure.parts[0] in FORBIDDEN_ROOTS or path in FORBIDDEN_FILES:
        return True
    if "__pycache__" in pure.parts or any(part.startswith(".env") for part in pure.parts):
        return True
    return pure.suffix.lower() in FORBIDDEN_SUFFIXES


def validate_release_candidate(
    package: dict[str, Any],
    pack: dict[str, Any],
    *,
    version: str,
    tracked_paths: Iterable[str],
    plugin_version: str,
    expected_version: str | None = None,
) -> list[str]:
    errors: list[str] = []
    files = {
        normalize_pack_path(str(entry.get("path", "")))
        for entry in pack.get("files", [])
        if entry.get("path")
    }
    tracked = {normalize_pack_path(path) for path in tracked_paths}
    candidate_version = expected_version or version

    if package.get("name") != "vidux":
        errors.append("package name must be 'vidux'")
    if package.get("private") is not False:
        errors.append("package.private must be false for a public release candidate")
    if package.get("version") != candidate_version:
        errors.append(
            f"package.json version {package.get('version')!r} does not match {candidate_version!r}"
        )
    if pack.get("version") != candidate_version:
        errors.append(f"packed version {pack.get('version')!r} does not match {candidate_version!r}")
    if plugin_version != candidate_version:
        errors.append(
            f"Claude plugin version {plugin_version!r} does not match {candidate_version!r}"
        )
    if package.get("bin") != {"vidux": "bin/vidux"}:
        errors.append("package bin must map 'vidux' to 'bin/vidux'")
    if not package.get("files"):
        errors.append("package files allowlist must be present and non-empty")
    if package.get("engines", {}).get("node") != ">=20":
        errors.append("package engines.node must be '>=20'")
    publish_config = package.get("publishConfig", {})
    if publish_config.get("access") != "public" or publish_config.get("provenance") is not True:
        errors.append("publishConfig must require public access and provenance")
    if package.get("scripts", {}).get("release:verify") != "python3 scripts/vidux-release-package.py":
        errors.append("package scripts.release:verify must run the release package verifier")

    missing = sorted(REQUIRED_FILES - files)
    if missing:
        errors.append("packed artifact is missing required files: " + ", ".join(missing))

    forbidden = sorted(path for path in files if is_forbidden(path))
    if forbidden:
        errors.append("packed artifact contains forbidden files: " + ", ".join(forbidden))

    unexpected_v3 = sorted(
        path for path in files if path.startswith("benchmarks/v3/") and path not in V3_ALLOWED_FILES
    )
    if unexpected_v3:
        errors.append(
            "packed artifact contains runtime or evaluator v3 files: "
            + ", ".join(unexpected_v3)
        )

    untracked = sorted(files - tracked)
    if untracked:
        errors.append("packed artifact contains files not tracked by git: " + ", ".join(untracked))

    file_count = len(files)
    if file_count > MAX_FILE_COUNT:
        errors.append(f"packed artifact has {file_count} files; limit is {MAX_FILE_COUNT}")
    unpacked_size = int(pack.get("unpackedSize", 0) or 0)
    if unpacked_size > MAX_UNPACKED_BYTES:
        errors.append(
            f"packed artifact is {unpacked_size} unpacked bytes; limit is {MAX_UNPACKED_BYTES}"
        )
    return errors


def run_json(command: list[str], *, cwd: Path) -> Any:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return json.loads(result.stdout)


def tracked_files(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed: {detail or result.returncode}")
    return {
        normalize_pack_path(path.decode("utf-8"))
        for path in result.stdout.split(b"\0")
        if path
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pack_once(root: Path, destination: Path) -> tuple[dict[str, Any], str]:
    rows = run_json(
        [
            "npm",
            "pack",
            "--json",
            "--ignore-scripts",
            "--pack-destination",
            str(destination),
        ],
        cwd=root,
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("npm pack returned an unexpected JSON payload")
    pack = rows[0]
    tarball = destination / str(pack.get("filename", ""))
    if not tarball.is_file():
        raise RuntimeError(f"npm pack did not create the reported tarball: {tarball}")
    return pack, sha256_file(tarball)


def verify(root: Path, *, expected_version: str | None = None) -> dict[str, Any]:
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    version = source_version(root)
    with tempfile.TemporaryDirectory(prefix="vidux-pack-") as temp:
        temp_root = Path(temp)
        first = temp_root / "first"
        second = temp_root / "second"
        first.mkdir()
        second.mkdir()
        pack, first_sha = pack_once(root, first)
        second_pack, second_sha = pack_once(root, second)
    errors = validate_release_candidate(
        package,
        pack,
        version=version,
        tracked_paths=tracked_files(root),
        plugin_version=str(plugin.get("version", "")),
        expected_version=expected_version,
    )
    if first_sha != second_sha:
        errors.append(
            "repeated npm pack runs were not byte-reproducible: "
            f"{first_sha} != {second_sha}"
        )
    if pack.get("files") != second_pack.get("files"):
        errors.append("repeated npm pack runs produced different file manifests")
    return {
        "ok": not errors,
        "name": pack.get("name"),
        "version": pack.get("version"),
        "filename": pack.get("filename"),
        "file_count": len(pack.get("files", [])),
        "packed_bytes": int(pack.get("size", 0) or 0),
        "unpacked_bytes": int(pack.get("unpackedSize", 0) or 0),
        "sha256": first_sha,
        "reproducible": first_sha == second_sha,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--expect-version")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        receipt = verify(args.root.resolve(), expected_version=args.expect_version)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        receipt = {"ok": False, "errors": [str(exc)]}

    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    elif receipt["ok"]:
        print(
            "vidux release package: OK "
            f"({receipt['version']}, {receipt['file_count']} files, "
            f"{receipt['unpacked_bytes']} unpacked bytes, sha256={receipt['sha256']})"
        )
    else:
        print("vidux release package: FAILED", file=sys.stderr)
        for error in receipt["errors"]:
            print(f"- {error}", file=sys.stderr)
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
