#!/usr/bin/env python3
"""Fail when retired project-board terms reappear in Vidux's current surface."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SCAN_TARGETS = (
    "SKILL.md",
    "README.md",
    "CONTRIBUTING.md",
    "commands",
    "docs",
    "guides",
    "scripts",
    ".github",
    "package.json",
)

EXCLUDED_DIR_NAMES = {".git", "__pycache__", "node_modules"}
EXCLUDED_RELATIVE_PATHS = {
    Path("docs/.vitepress"),
    Path("scripts/vidux-public-ready-grep-gate.py"),
    Path("tests/test_public_ready_grep_gate.py"),
}

FORBIDDEN_PATTERNS = (
    ("retired board brand", re.compile(r"\bLinear\b")),
    ("retired board lowercase", re.compile(r"\blinear\b")),
    ("retired GitHub Projects config key", re.compile(r"\bgh_projects\b")),
    ("retired inbox source config key", re.compile(r"\binbox_sources\b")),
    ("retired external-state label", re.compile(r"\bexternal-state\b")),
    ("retired inbox sync script", re.compile(r"\bvidux-inbox-sync\b")),
    ("retired audit script", re.compile(r"\blinear-audit\b")),
    ("retired pilot path", re.compile(r"\bpilot/")),
    ("private Leo Flow lane", re.compile(r"\bLeo Flow\b")),
    ("private slop lane", re.compile(r"/ai-slop\b")),
    ("retired hosted routines wording", re.compile(r"\bClaude Routines\b")),
    ("private vidux overlay name", re.compile(r"/vidux-leo\b")),
    ("private home path", re.compile(r"/Users/(?:leokwan|redacted-operator)\b")),
    ("employer source path", re.compile(r"\bREDACTED-EMPLOYER-PATH/Dev\b")),
    ("private skills repo path", re.compile(r"\bDevelopment/ai(?:-leo)?/(?:hooks|skills)\b")),
)


def _is_excluded(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root)
    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
        return True
    return any(rel == excluded or excluded in rel.parents for excluded in EXCLUDED_RELATIVE_PATHS)


def _drop_git_ignored(repo_root: Path, files: list[Path]) -> list[Path]:
    """Scan only what ships. Drop git-ignored files (Leo keeps private tooling on
    disk locally); no-op outside a git repo so tmp-dir tests still scan all files."""
    try:
        inside = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=False,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return files
        rels = [str(f.relative_to(repo_root)) for f in files]
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "check-ignore", "--stdin"],
            input="\n".join(rels), capture_output=True, text=True, check=False,
        )
        ignored = set(proc.stdout.splitlines())
        return [f for f, rel in zip(files, rels) if rel not in ignored]
    except Exception:
        return files


def _iter_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        path = repo_root / target
        if not path.exists():
            continue
        if path.is_file():
            if not _is_excluded(path, repo_root):
                files.append(path)
            continue
        for child in path.rglob("*"):
            if child.is_file() and not _is_excluded(child, repo_root):
                files.append(child)
    return _drop_git_ignored(repo_root, sorted(files))


def run_gate(repo_root: Path) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    scanned_files = _iter_files(repo_root)
    for path in scanned_files:
        rel = path.relative_to(repo_root)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, start=1):
            for label, pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    matches.append(
                        {
                            "file": str(rel),
                            "line": lineno,
                            "pattern": label,
                            "text": line.strip(),
                        }
                    )

    return {
        "status": "failed" if matches else "passed",
        "scanned_files": len(scanned_files),
        "matches": matches,
    }


def _human(payload: dict[str, Any]) -> str:
    lines = [
        "Vidux public-ready grep gate",
        f"status: {payload['status']}",
        f"scanned_files: {payload['scanned_files']}",
    ]
    if payload["matches"]:
        lines.append("matches:")
        for match in payload["matches"]:
            lines.append(
                f"- {match['file']}:{match['line']} "
                f"[{match['pattern']}] {match['text']}"
            )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Vidux repo root. Defaults to this script's parent repo.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_gate(args.repo_root.resolve())
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_human(payload), end="")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
