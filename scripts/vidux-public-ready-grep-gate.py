#!/usr/bin/env python3
"""Fail when retired project-board terms reappear in Vidux's current surface."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


# Round-4 panel finding (2026-07-09): SCAN_TARGETS used to be a
# hand-maintained ALLOWLIST of top-level files/dirs. That design has already
# let a real, live leak ship unscanned twice before (ASK-LEO.md, `projects/`)
# and recurred a third time (AGENTS.md, CHANGELOG.md were simply never named
# here) -- an allowlist only protects what someone remembered to add, and a
# new/renamed top-level file ships unscanned by default until a future panel
# round notices. Scanning is now DEFAULT-ON: everything tracked is scanned
# unless it's named in the denylist below, so a new file is covered the
# moment it's created.
EXCLUDED_DIR_NAMES = {".git", "__pycache__", "node_modules"}
EXCLUDED_RELATIVE_PATHS = {
    # Round-6 panel finding: a bare `Path("docs/.vitepress")` entry used to
    # sit here, exempting the entire tree -- the identical "whole directory,
    # not the one file that needs it" bug just fixed for tests/, one entry
    # over. Checked: docs/.vitepress/dist/ is already git-ignored (dropped
    # by _drop_git_ignored below without needing an exemption) and
    # docs/.vitepress/config.ts -- the only tracked file in the tree --
    # contains zero content that trips any FORBIDDEN_PATTERN. No exemption
    # is actually needed here; the entry is removed rather than narrowed.
    #
    # This script's own comments and the test file below intentionally pin
    # the forbidden strings verbatim as documentation/fixtures, not leaks.
    Path("scripts/vidux-public-ready-grep-gate.py"),
    Path("tests/test_public_ready_grep_gate.py"),
    # tests/test_vidux_contracts.py legitimately pins some of these strings
    # as required test content (the private-path contract tests) -- scanning
    # it would flag the test file, not a leak.
    #
    # Round-5 panel finding (found independently by 2 lenses): this used to
    # be the bare directory `Path("tests")`, exempting all 36 tracked files
    # under tests/ -- not just these 2 -- from every FORBIDDEN_PATTERN,
    # including PRIVACY_PATTERNS. Reproduced live: a scratch file dropped
    # into tests/ containing real employer-path/email leak-class strings
    # passed the gate with zero matches. Same "allowlist only protects what
    # someone remembered to add" failure the round-4 SCAN_TARGETS redesign
    # was built to eliminate, reintroduced one directory level down via an
    # over-broad denylist entry. Narrowed to exactly the 2 files that need it.
    Path("tests/test_vidux_contracts.py"),
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
    # Round-8 panel finding: 4 evidence files named the maintainer's real
    # spouse by first name -- once in a genuinely sensitive context (a
    # confidential job-search screenshot, now purged from the branches
    # that carried it), the rest as a recurring "make this simple enough
    # for X" persona shorthand. No PRIVACY_PATTERNS rule existed for a
    # family member's name at all. Placeholder-safe: this name never
    # appears in this repo's own shipped code/docs otherwise, so the
    # false-positive risk is the same as any other named-individual rule
    # already in this list.
    # Round-9 panel finding: the round-8 rule had no re.IGNORECASE, so it
    # only ever matched the capitalized prose form and gave false
    # confidence -- the dominant lowercase/kebab-case usage (this repo's
    # own project-naming convention lowercases everything, e.g.
    # "family-member-fpa-ai") sailed through every prior grep-gate run
    # unnoticed. Added re.IGNORECASE to match every casing.
    ("maintainer's spouse's first name", re.compile(r"\bNicole\b", re.IGNORECASE)),
    # Round-3 panel finding: this rule's own regex had been over-redacted to
    # the literal placeholder text "REDACTED-EMPLOYER-PATH" -- a string that
    # never appears in real content, so the check was a permanent silent
    # no-op. It missed a live leak: this session's own evidence file quoting
    # the maintainer's real employer-issued-laptop home path and corporate
    # email verbatim while documenting a confidentiality finding about that
    # exact content.
    ("employer source path", re.compile(r"\b(?:lkwan|Snapchat/Dev)\b")),
    # Bare-domain form, not just the `@`-prefixed email form -- a real
    # instance found live was an internal registry hostname with no `@`.
    ("employer email or domain", re.compile(r"\bsnapchat\.com\b", re.IGNORECASE)),
    ("employer internal hostname", re.compile(r"\bsc-corp\.net\b", re.IGNORECASE)),
    # Round-7 panel finding: no rule existed for the employer's internal
    # `.snap` TLD (distinct from the public `snapchat.com` domain above) --
    # a real instance (an internal inference-service hostname) shipped
    # unredacted in a tracked evidence file and this gate reported "passed"
    # with zero matches.
    #
    # Round-9 panel finding: the comments above and this rule's own test
    # fixtures used to reproduce the actual leaked strings verbatim
    # (a real coworker's email, a real internal hostname) -- gratuitous,
    # since these regexes match on domain/TLD only and a synthetic example
    # exercises them identically without adding a second, avoidable copy of
    # someone else's PII to the repo. Comments and fixtures now use made-up
    # placeholders; only the regex patterns themselves need the real
    # domain/TLD strings to detect a leak.
    ("employer internal .snap TLD", re.compile(r"\.snap\b", re.IGNORECASE)),
    # Round-7 panel finding: no rule existed for a gmail address or the
    # maintainer's separate small consumer-goods business name -- both
    # leaked live in commit-message quotes inside tracked evidence files,
    # unscanned because PRIVACY_PATTERNS had no entry for either.
    # `leojkwan@gmail.com` is excluded: it's the maintainer's permanent,
    # by-design public commit-author identity on every commit on
    # `origin/main` today (confirmed via `git log --format='%ae'`) -- unlike
    # every other gmail address, it isn't slated for removal/rewrite, so
    # quoting it in evidence prose adds no incremental exposure.
    ("gmail address other than the maintainer's public commit identity",
     re.compile(r"\b(?!leojkwan@gmail\.com\b)[\w.+-]+@gmail\.com\b", re.IGNORECASE)),
    ("maintainer's other business name", re.compile(r"\btrysnowcubes\b", re.IGNORECASE)),
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
#
# ARCHIVE.md and CHANGELOG.md were previously excluded from scanning
# entirely on the theory that "true history/changelog files record retired
# terms in legitimate past tense". That's a real concern (both files do
# legitimately mention retired terms like "Linear" many times in past
# tense) but full exclusion also hid real PRIVACY_PATTERNS leaks in
# CHANGELOG.md (found in the same 2026-07-09 panel round) -- the fix is the
# same one already applied to PLAN.md/ASK-LEO.md/projects: HISTORICAL_
# TARGETS membership, not exclusion. Privacy leaks aren't legitimate in any
# tense; retired-terminology hygiene noise is the only thing past tense
# excuses.
HISTORICAL_TARGETS = {
    "evidence",
    "investigations",
    "PLAN.md",
    "projects",
    "ASK-LEO.md",
    "ARCHIVE.md",
    "CHANGELOG.md",
}
# Round-7 panel finding (P1, documented, NOT fixed): "PLAN.md" and "projects"
# are whole-file/whole-directory HYGIENE_PATTERNS exemptions, but a PLAN.md
# is not append-only-by-design the way CHANGELOG.md/ARCHIVE.md genuinely
# are -- it's a living document with LIVE sections (Purpose, Constraints,
# Tasks, Open work) interleaved with append-only sections (Decision Log,
# Progress, Drift Log). Reproduced live: injecting a HYGIENE_PATTERNS
# violation into projects/artifact-self-improvement/PLAN.md's ACTIVE Tasks
# section still reports "passed", because the whole file (root PLAN.md and
# every projects/*/PLAN.md alike) is exempted regardless of which section a
# line falls in. PRIVACY_PATTERNS still catch a real leak anywhere in these
# files (see docstring above) -- this gap is HYGIENE_PATTERNS only (retired-
# terminology accuracy, not a privacy/security leak). A correct fix needs
# section-aware scanning (treat only recognized append-only headings --
# "Decision Log", "Progress", "Drift Log" -- as historical, scan everything
# else in a PLAN.md normally) rather than whole-file classification. Not
# implemented yet: it changes scanning behavior for every PLAN.md in the
# repo and deserves its own dedicated verification pass rather than a rushed
# change alongside this round's other fixes.


# Files where "linear"/"Linear" is unrelated domain vocabulary (a CSS
# gradient/timing-function keyword, a secret-scanner rule name describing
# what it detects) rather than a mention of the retired Linear.app board
# integration. Found by the round-4 default-on scan surfacing 9 new matches
# the moment style/tooling-config files were scanned for the first time --
# all 9 were this class, zero were real. PRIVACY_PATTERNS still apply to
# these files (a leaked path/username is not exempt just because the file
# is CSS); only the retired-terminology HYGIENE_PATTERNS are skipped.
HYGIENE_EXEMPT_SUFFIXES = {".css", ".svg"}
HYGIENE_EXEMPT_NAMES = {".gitignore", ".gitleaks.toml"}


def _is_historical(rel: Path) -> bool:
    return rel.parts[0] in HISTORICAL_TARGETS


def _hygiene_exempt(rel: Path) -> bool:
    return rel.suffix in HYGIENE_EXEMPT_SUFFIXES or rel.name in HYGIENE_EXEMPT_NAMES


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


def _tracked_files(repo_root: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--cached", "-z"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("--tracked-only requires a git worktree")
    files = []
    for raw_rel in proc.stdout.split(b"\0"):
        if not raw_rel:
            continue
        path = repo_root / raw_rel.decode("utf-8", errors="surrogateescape")
        if not _is_excluded(path, repo_root):
            files.append(path)
    return sorted(files)


def _iter_files(repo_root: Path, *, tracked_only: bool = False) -> list[Path]:
    if tracked_only:
        return _tracked_files(repo_root)
    files = [
        child
        for child in repo_root.rglob("*")
        if child.is_file() and not _is_excluded(child, repo_root)
    ]
    return _drop_git_ignored(repo_root, sorted(files))


def _read_scanned_lines(path: Path, repo_root: Path, *, tracked_only: bool) -> list[str]:
    if not tracked_only:
        return path.read_text(encoding="utf-8").splitlines()
    rel = path.relative_to(repo_root).as_posix()
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "show", f":{rel}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise OSError(f"cannot read staged content for {rel}")
    return proc.stdout.decode("utf-8").splitlines()


def run_gate(repo_root: Path, *, tracked_only: bool = False) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    try:
        scanned_files = _iter_files(repo_root, tracked_only=tracked_only)
    except RuntimeError as exc:
        return {
            "status": "failed",
            "scope": "tracked" if tracked_only else "working-tree",
            "scanned_files": 0,
            "matches": [],
            "errors": [str(exc)],
        }
    for path in scanned_files:
        rel = path.relative_to(repo_root)
        # Round-7 panel finding: this loop only ever checked file *content*
        # -- the relative path/filename itself was never matched against
        # any pattern. Reproduced live: an evidence file's body was
        # redacted but its filename still carried a leak-class string
        # verbatim, which renders unredacted in any GitHub directory
        # listing regardless of what's inside the file. PRIVACY_PATTERNS
        # (not HYGIENE_PATTERNS -- a filename containing "linear" is noise,
        # not a leak) apply to every filename unconditionally, including
        # historical/hygiene-exempt files: a leak in a filename is exactly
        # as visible whether or not the file's own content is exempt.
        rel_str = str(rel)
        for label, pattern in PRIVACY_PATTERNS:
            if pattern.search(rel_str):
                matches.append(
                    {
                        "file": rel_str,
                        "line": 0,
                        "pattern": f"{label} (in filename)",
                        "text": rel_str,
                    }
                )
        patterns = (
            PRIVACY_PATTERNS
            if _is_historical(rel) or _hygiene_exempt(rel)
            else FORBIDDEN_PATTERNS
        )
        try:
            lines = _read_scanned_lines(path, repo_root, tracked_only=tracked_only)
        except UnicodeDecodeError:
            continue
        except OSError:
            # Round-5 panel finding: an unreadable file (permissions) or one
            # deleted between _iter_files() listing and this read (plausible
            # if the gate runs while other automation is writing to
            # evidence/) previously propagated as an unhandled traceback --
            # exit 1 either way, indistinguishable from a real leak match to
            # a caller checking only the exit code, and --json mode emitted
            # no parseable output at all. Treat as unscannable, not fatal.
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
        "scope": "tracked" if tracked_only else "working-tree",
        "scanned_files": len(scanned_files),
        "matches": matches,
        "errors": [],
    }


def _human(payload: dict[str, Any]) -> str:
    lines = [
        "Vidux public-ready grep gate",
        f"status: {payload['status']}",
        f"scope: {payload['scope']}",
        f"scanned_files: {payload['scanned_files']}",
    ]
    for error in payload.get("errors", []):
        lines.append(f"error: {error}")
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
    parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="Scan the tracked/staged shipping set instead of every unignored worktree file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_gate(args.repo_root.resolve(), tracked_only=args.tracked_only)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_human(payload), end="")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
