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
    "PLAN.md",
    "ASK-LEO.md",
    "commands",
    "docs",
    "guides",
    "scripts",
    "prompts",
    "evidence",
    "investigations",
    "projects",
    ".github",
    "package.json",
    # Deliberately NOT scanned:
    # - "tests" is excluded: tests/test_vidux_contracts.py legitimately pins
    #   some of these strings as required test content (see the private-path
    #   contract tests); scanning it would flag the test file, not a leak.
    # - True history/changelog files (ARCHIVE.md, CHANGELOG.md) record
    #   retired terms (e.g. "Linear") in legitimate past tense; scanning them
    #   against FORBIDDEN_PATTERNS produces noise, not real findings.
    #
    # "projects" IS scanned (added after a 2026-07-09 panel round found a
    # live leak in a tracked exception: `!projects/night-queue/` shipped
    # Snap-corporate paths untouched because the gate skipped the whole
    # directory). `_drop_git_ignored` already keeps this safe: the untracked
    # bulk of the private plan store (`projects/*` minus named exceptions)
    # never reaches the scan, only what's actually going to ship does. It's
    # also in HISTORICAL_TARGETS below, so retired-terminology hygiene
    # patterns still don't fire on old plan dirs (test_historical_plan_dirs_
    # are_out_of_scope covers exactly this).
    #
    # ASK-LEO.md IS scanned (added after the same 2026-07-09 panel round):
    # it was previously grouped with ARCHIVE.md/CHANGELOG.md as a "history
    # file", but per its own header it's a LIVE, ongoing queue ("durable
    # queue of questions the fleet has for Leo") that accumulates new
    # entries, not a closed historical record -- and a real private
    # home-path + private-overlay-name leak sat in it, unscanned, the whole
    # time. It's in HISTORICAL_TARGETS below so its resolved Q&A entries
    # don't trip HYGIENE_PATTERNS, but PRIVACY_PATTERNS apply to it like
    # everything else.
)

EXCLUDED_DIR_NAMES = {".git", "__pycache__", "node_modules"}
EXCLUDED_RELATIVE_PATHS = {
    Path("docs/.vitepress"),
    Path("scripts/vidux-public-ready-grep-gate.py"),
    Path("tests/test_public_ready_grep_gate.py"),
}

# Privacy/PII/confidentiality patterns: enforced everywhere scanned,
# regardless of tense. A personal home path or an employer-internal path
# is unsafe to publish whether it appears in live doctrine or a dated
# historical record.
PRIVACY_PATTERNS = (
    # Round-3 panel finding: this pattern originally only matched the spaced
    # "Leo Flow" form and missed the hyphenated slash-command form actually
    # used in prose ("/leo-flow", "leo-flow") -- 6 live occurrences in
    # SKILL.md's own doctrine section passed the gate green while the exact
    # leak class this pattern exists to catch sat in the flagship file.
    ("private Leo Flow lane", re.compile(r"\bLeo[ -]Flow\b", re.IGNORECASE)),
    ("private slop lane", re.compile(r"/ai-slop\b")),
    ("private vidux overlay name", re.compile(r"/vidux-leo\b")),
    # Round-3 panel finding: the old pattern only matched the /Users/leokwan
    # PATH form and missed the maintainer's bare username elsewhere -- a
    # historical evidence file leaked 26 `com.leokwan.<private-project>`
    # macOS LaunchAgent labels (naming several unrelated private repos) and
    # a live setup doc leaked one more, both unscanned because neither is a
    # /Users/ path. \bleokwan\b / \bredacted-operator\b subsumes the old path form (a
    # path boundary is also a \b boundary) while also catching every bare
    # mention.
    ("private username", re.compile(r"\b(?:leokwan|redacted-operator)\b")),
    ("employer source path", re.compile(r"\bREDACTED-EMPLOYER-PATH/Dev\b")),
    ("private skills repo path", re.compile(r"\bDevelopment/ai(?:-leo)?/(?:hooks|skills)\b")),
)

# Retired-terminology hygiene patterns: only meaningful as a "don't market
# a retired integration as current" check against LIVE-facing docs. A past
# -tense mention in a dated historical record (evidence/, investigations/,
# or PLAN.md's append-only Decision Log) is the record doing its job, not
# a leak — see HISTORICAL_TARGETS below.
HYGIENE_PATTERNS = (
    ("retired board brand", re.compile(r"\bLinear\b")),
    ("retired board lowercase", re.compile(r"\blinear\b")),
    ("retired GitHub Projects config key", re.compile(r"\bgh_projects\b")),
    ("retired inbox source config key", re.compile(r"\binbox_sources\b")),
    ("retired external-state label", re.compile(r"\bexternal-state\b")),
    ("retired inbox sync script", re.compile(r"\bvidux-inbox-sync\b")),
    ("retired audit script", re.compile(r"\blinear-audit\b")),
    ("retired pilot path", re.compile(r"\bpilot/")),
    ("retired hosted routines wording", re.compile(r"\bClaude Routines\b")),
)

FORBIDDEN_PATTERNS = PRIVACY_PATTERNS + HYGIENE_PATTERNS

# Historical-record targets: chronological, dated, append-only-by-design.
# HYGIENE_PATTERNS are skipped here (retired terms in past tense are the
# record working correctly); PRIVACY_PATTERNS still apply everywhere.
HISTORICAL_TARGETS = {"evidence", "investigations", "PLAN.md", "projects", "ASK-LEO.md"}


def _is_historical(rel: Path) -> bool:
    return rel.parts[0] in HISTORICAL_TARGETS


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
        patterns = PRIVACY_PATTERNS if _is_historical(rel) else FORBIDDEN_PATTERNS
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, start=1):
            for label, pattern in patterns:
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
