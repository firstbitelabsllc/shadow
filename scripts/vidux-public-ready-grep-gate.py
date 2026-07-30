#!/usr/bin/env python3
"""Fail when retired project-board terms reappear in Vidux's current surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


# SCAN_TARGETS used to be a
# hand-maintained ALLOWLIST of top-level files/dirs. That design has already
# let a real, live leak ship unscanned twice before (ASK-LEO.md, `projects/`)
# and recurred a third time (AGENTS.md, CHANGELOG.md were simply never named
# here) -- an allowlist only protects what someone remembered to add, and a
# new/renamed top-level file ships unscanned by default until someone
# notices. Scanning is now DEFAULT-ON: everything tracked is scanned
# unless it's named in the denylist below, so a new file is covered the
# moment it's created.
EXCLUDED_DIR_NAMES = {".git", "__pycache__", "node_modules"}
EXCLUDED_RELATIVE_PATHS: set[Path] = set()

# Purist-cut artifacts are forbidden by path, not just by package allowlist.
# This catches a restored file even when its contents contain no searchable
# marker. Historical prose may still explain why the subsystem was removed.
REMOVED_ARTIFACT_PATHS = {Path("browser/run_extract_pass.py")}
REMOVED_ARTIFACT_PREFIXES = (
    Path("agent"),
    Path("browser/receipts"),
    Path("commands"),
)

# Fragment private product markers so this file's own source does not contain
# a contiguous matchable token for rules that would otherwise self-hit.
_PRIVATE_FLOW_LANE = "Leo" + " Flow"
_PRIVATE_FLOW_HYPHEN = "leo" + "-flow"
_PRIVATE_SLOP_LANE = "/" + "ai-slop"
_PRIVATE_VIDUX_OVERLAY = "/" + "vidux-leo"
_PRIVATE_PILOT_OVERLAY = "pilot" + "-leo"

# Privacy/PII/confidentiality patterns: enforced everywhere scanned,
# regardless of tense. Category-based and synthetic-safe: no personal names,
# employer brands, machine-local emails, or private business names appear as
# detection literals. A personal home path or private snapshot is unsafe to
# publish whether it appears in live doctrine or a dated historical record.
#
# Pattern labels intentionally avoid the matchable surface of their own rules
# (never put the matchable phrase itself into a label or comment).
PRIVACY_PATTERNS = (
    # Private product lane / overlay markers used by this repo's surface.
    (
        "private flow-lane marker",
        re.compile(
            rf"\b(?:{re.escape(_PRIVATE_FLOW_LANE)}|{re.escape(_PRIVATE_FLOW_HYPHEN)})\b",
            re.IGNORECASE,
        ),
    ),
    ("private slop-lane marker", re.compile(re.escape(_PRIVATE_SLOP_LANE) + r"\b")),
    (
        "private overlay marker",
        re.compile(re.escape(_PRIVATE_VIDUX_OVERLAY) + r"\b"),
    ),
    # Absolute POSIX home directories for any username, not one operator.
    (
        "absolute home path",
        re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/"),
    ),
    # Home-relative paths that expose private local structure.
    # Intentionally excludes publicly documented product paths such as
    # ~/Development/vidux and ~/.config/vidux.
    (
        "home-relative private path",
        re.compile(
            r"~/(?:Documents|Library|Desktop|Downloads|"
            r"\.ssh|\.aws|\.gnupg)/"
        ),
    ),
    # Non-public email addresses. Allowlisted public identities are filtered
    # in _privacy_hits (metadata allowlist is the single source of truth for
    # the repository's public commit identity).
    (
        "non-public email address",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    # Credential / auth material by structural field shape.
    (
        "credential-field payload",
        re.compile(
            r'"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|'
            r'client[_-]?secret|id_token|private_key)"\s*:\s*"[^"]+"',
            re.IGNORECASE,
        ),
    ),
    # Quota / roster / account snapshots by structural field or prose category.
    (
        "category_quota_payload",
        re.compile(
            r'(?:'
            r'"(?:quota_remaining|remaining_percent|roster|'
            r'seat_roster|account_roster)"\s*:'
            r'|'
            r'\b(?:quota|roster|auth)\s+(?:snapshot|dump|export|payload)\b'
            r')',
            re.IGNORECASE,
        ),
    ),
    # Raw chat / transcript / session dumps by prose category.
    # Structural chat message JSON is not matched: this product legitimately
    # tests and documents role/content shapes.
    (
        "category_transcript_payload",
        re.compile(
            r'\b(?:raw\s+)?(?:chat|conversation|session)\s+'
            r'(?:transcript|dump|export)\b',
            re.IGNORECASE,
        ),
    ),
    # Private finance / account material by category (not provider brands).
    # Avoid bare "account balance" prose — redaction tests mention it without
    # shipping finance data.
    (
        "finance-account payload",
        re.compile(
            r'(?:'
            r'\b(?:bank\s+account\s+number|routing\s+number|tax\s+id)\b'
            r'|'
            r'"(?:account_number|routing_number|balance_cents|iban)"\s*:'
            r')',
            re.IGNORECASE,
        ),
    ),
    # Structural private skills path (no operator username).
    (
        "private skills-path marker",
        re.compile(
            r"\b(?:Development|Documents)/(?:ai(?:-leo)?|skills)/(?:hooks|skills)\b"
        ),
    ),
    (
        "private machine-ownership assignment",
        re.compile(
            r"(?:"
            r"\b(?:Mac Studio|M[1-9]\s+(?:Pro|Max|Ultra)|this Mac)\b[^\n]{0,100}"
            r"(?:\bowns\b|\bowned\b|\bassigned\b|"
            r"\b(?:does not|must not|never)\b[^\n]{0,40}\b(?:probe|edit|open|run)\b)"
            r"|"
            r"(?:\bowns\b|\bowned\b|\bassigned\b|"
            r"\b(?:does not|must not|never)\b[^\n]{0,40}\b(?:probe|edit|open|run)\b)"
            r"[^\n]{0,100}\b(?:Mac Studio|M[1-9]\s+(?:Pro|Max|Ultra)|this Mac)\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "private project category path",
        re.compile(
            r"\bprojects/[A-Za-z0-9._-]+-(?:personal|family|finance|career)"
            r"(?:/|\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "named-person private context",
        re.compile(
            r"(?:"
            r"\b(?:persona|wife|husband|spouse|partner|daughter|son|"
            r"mother|father)\s*(?:name\s*)?(?:is|[:=])\s*[\"'`]*"
            r"[A-Z][a-z]{2,}\b"
            r"|"
            r"\b[A-Z][a-z]{2,}\s+is\s+(?:my|the user's)\s+"
            r"(?:wife|husband|spouse|partner|daughter|son|mother|father)\b"
            r"|"
            r"\b(?:for|about)\s+[A-Z][a-z]{2,}[’']s\s+"
            r"(?:personal|family|career|financ(?:e|ial))\b"
            r")"
        ),
    ),
    (
        "private organization marker",
        re.compile(
            r"(?:"
            r"[\"'](?:business|brand|company)(?:_name)?[\"']\s*:\s*"
            r"[\"'][^\"'\n]{2,}[\"']"
            r"|"
            r"\b(?:private|personal|family)\s+(?:business|brand|company)"
            r"\s*(?:is|[:=])\s*[\"'`]*[A-Z][A-Za-z0-9& .-]{1,80}"
            r")",
        ),
    ),
    (
        "private launch service label",
        re.compile(
            r"\b(?:launchctl|LaunchAgent)\b[^\n]{0,160}"
            r"\b(?:com|net|org|io|ai|dev)\.[a-z0-9][a-z0-9.-]+\b",
            re.IGNORECASE,
        ),
    ),
)

# Retired-terminology hygiene patterns: only meaningful as a "don't market
# a retired integration as current" check against LIVE-facing docs. A past
# -tense mention in a dated historical record (evidence/, investigations/,
# or PLAN.md's append-only Decision Log) is the record doing its job, not
# a leak — see HISTORICAL_TARGETS below.
HYGIENE_PATTERNS = (
    (
        "private pilot overlay",
        re.compile(rf"\b{re.escape(_PRIVATE_PILOT_OVERLAY)}\b", re.IGNORECASE),
    ),
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

# Commit-identity allowlist for the metadata scan (--metadata) and for the
# non-public-email privacy rule. A public repo publishes every reachable
# commit's author/committer email, and a foreign identity renders a real,
# unrelated GitHub account as a public contributor. Only these identities are
# legitimate public commit participants:
#   - leojkwan@gmail.com: maintainer public commit identity on origin/main
#   - noreply@github.com: GitHub web-UI / squash-merge committer identity
#   - codesmith-bot@users.noreply.github.com: Codesmith autofix / review bot
#   - cursoragent@cursor.com: Cursor agent committer identity
# Machine-local emails and private account addresses are intentionally absent.
ALLOWED_COMMIT_EMAILS = frozenset(
    {
        "leojkwan@gmail.com",
        "noreply@github.com",
        "codesmith-bot@users.noreply.github.com",
        "cursoragent@cursor.com",
    }
)

# One machine-local identity was already published before metadata enforcement.
# Scope the waiver to its exact immutable commit, role, and normalized digest so
# the same address cannot authorize a new commit, trailer, or different role.
LEGACY_COMMIT_IDENTITY_WAIVERS = frozenset(
    {
        (
            "d79cfb869cc6f9d5c886f85e82df8553cd41bc49",
            "author",
            "c535b8d5ff96384e34e93c92085ea40bad15b20f97b9733aa719c1043f1ff9b8",
        ),
        (
            "d79cfb869cc6f9d5c886f85e82df8553cd41bc49",
            "committer",
            "c535b8d5ff96384e34e93c92085ea40bad15b20f97b9733aa719c1043f1ff9b8",
        ),
    }
)

# Domains commonly used in public documentation / synthetic fixtures.
# Kept separate from commit-identity allowlisting so docs can show
# user@example.com without a false privacy hit, while still catching
# non-public addresses. Reserved TLDs (.invalid/.test/.example/.localhost)
# are handled in _email_is_allowed.
ALLOWED_EMAIL_DOMAINS = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "localhost",
    }
)
_RESERVED_EMAIL_TLDS = (".invalid", ".test", ".example", ".localhost")

# Absolute network references are public surface too. A new external host must
# be consciously added here; arbitrary intranet, private DNS, and raw LAN
# addresses fail. Reserved documentation domains and loopback are synthetic
# development fixtures, not routable private hosts.
ALLOWED_PUBLIC_HOSTS = frozenset(
    {
        "127.0.0.1",
        "0.0.0.0",
        "claude.ai",
        "cdn.jsdelivr.net",
        "docs.lovable.dev",
        "docs.openhands.dev",
        "docs.replit.com",
        "example.com",
        "example.net",
        "example.org",
        "github.com",
        "img.shields.io",
        "json-schema.org",
        "json.schemastore.org",
        "keepachangelog.com",
        "localhost",
        "opencollective.com",
        "registry.npmjs.org",
        "semver.org",
        "tidelift.com",
        "vidux.dev",
        "www.apache.org",
        "www.contributor-covenant.org",
        "www.w3.org",
    }
)
_RESERVED_HOST_SUFFIXES = (".example", ".invalid", ".test", ".localhost")
ABSOLUTE_URL_RE = re.compile(r"https?://[^\s<>{}\[\]\"'`]+", re.IGNORECASE)
HOST_FIELD_RE = re.compile(
    r"(?:[\"'](?:host|hostname|domain)[\"']|"
    r"\b(?:host|hostname|domain)\b)\s*[:=]\s*[\"']"
    r"(?P<host>[^\"'\s/]+)[\"']",
    re.IGNORECASE,
)

CO_AUTHOR_TRAILER_RE = re.compile(
    r"^\s*Co-authored-by:\s*(?P<name>.*?)\s*<(?P<email>[^>]+)>", re.IGNORECASE
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Historical-record targets: chronological, dated, append-only-by-design.
# HYGIENE_PATTERNS are skipped here (retired terms in past tense are the
# record working correctly); PRIVACY_PATTERNS still apply everywhere.
#
# ARCHIVE.md and CHANGELOG.md were previously excluded from scanning
# entirely on the theory that "true history/changelog files record retired
# terms in legitimate past tense". That's a real concern (both files do
# legitimately mention retired terms like "Linear" many times in past
# tense) but full exclusion also hid real PRIVACY_PATTERNS leaks in
# CHANGELOG.md -- the fix is the
# same one already applied to PLAN.md/ASK-LEO.md/projects: HISTORICAL_
# TARGETS membership, not exclusion. Privacy leaks aren't legitimate in any
# tense; retired-terminology hygiene noise is the only thing past tense
# excuses.
HISTORICAL_TARGETS = {
    "evidence",
    "investigations",
    "PLAN.md",
    "projects",
    "ASK-OWNER.md",
    "ASK-LEO.md",
    "ARCHIVE.md",
    "CHANGELOG.md",
}
# PLAN.md is a living document with current sections interleaved with
# append-only history. Only these sections, including their nested headings,
# receive the historical hygiene exemption. The next peer or parent heading
# returns scanning to the live policy.
PLAN_APPEND_ONLY_HEADINGS = {"decision log", "decisions", "drift log", "progress"}
MARKDOWN_HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
MARKDOWN_FENCE_RE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})")
MARKDOWN_SETEXT_RE = re.compile(r"^[ ]{0,3}(?P<marks>=+|-+)[ \t]*$")


# Files where "linear"/"Linear" is unrelated domain vocabulary (a CSS
# gradient/timing-function keyword, a secret-scanner rule name describing
# what it detects) rather than a mention of the retired Linear.app board
# integration. Found when default-on scanning first surfaced 9 new matches
# the moment style/tooling-config files were scanned for the first time --
# all 9 were this class, zero were real. PRIVACY_PATTERNS still apply to
# these files (a leaked path is not exempt just because the file is CSS);
# only the retired-terminology HYGIENE_PATTERNS are skipped.
#
# This gate script is hygiene-exempt for the same reason: it must document
# retired board terms. The gate's unit test is likewise hygiene-exempt because
# it constructs those fixtures. Privacy rules still apply to both files; hostile
# regression tests prove an unrelated privacy category cannot hide there.
HYGIENE_EXEMPT_SUFFIXES = {".css", ".svg"}
HYGIENE_EXEMPT_NAMES = {
    ".gitignore",
    ".gitleaks.toml",
    "test_public_ready_grep_gate.py",
    "vidux-public-ready-grep-gate.py",
}


def _is_historical(rel: Path) -> bool:
    return rel.parts[0] in HISTORICAL_TARGETS


def _hygiene_exempt(rel: Path) -> bool:
    return rel.suffix in HYGIENE_EXEMPT_SUFFIXES or rel.name in HYGIENE_EXEMPT_NAMES


def _email_is_allowed(email: str) -> bool:
    """Content-scan allow for non-public-email privacy hits."""
    lowered = email.strip().casefold()
    if lowered in {item.casefold() for item in ALLOWED_COMMIT_EMAILS}:
        return True
    if "@" not in lowered:
        return False
    domain = lowered.rsplit("@", 1)[1]
    if domain in ALLOWED_EMAIL_DOMAINS:
        return True
    # RFC 2606 / 6761 reserved names used only as synthetic fixtures in docs/tests.
    return any(domain == tld[1:] or domain.endswith(tld) for tld in _RESERVED_EMAIL_TLDS)


def _legacy_identity_digest_allowed(commit_sha: str, role: str, digest: str) -> bool:
    """Return whether an exact historical commit-role-digest tuple is waived."""
    return (commit_sha, role, digest) in LEGACY_COMMIT_IDENTITY_WAIVERS


def _commit_identity_allowed(email: str, *, commit_sha: str, role: str) -> bool:
    """Metadata allowlist for author/committer/trailer identities.

    Public identities are explicit. One already-published legacy identity is
    accepted by digest; this prevents a category-wide ``*.local`` bypass.
    """
    lowered = email.strip().casefold()
    if lowered in {item.casefold() for item in ALLOWED_COMMIT_EMAILS}:
        return True
    digest = hashlib.sha256(lowered.encode("utf-8")).hexdigest()
    return _legacy_identity_digest_allowed(commit_sha, role, digest)


def _privacy_hits(label: str, pattern: re.Pattern[str], text: str) -> bool:
    """Return True when *text* contains a privacy hit for *label*/*pattern*."""
    if label != "non-public email address":
        return pattern.search(text) is not None
    for match in pattern.finditer(text):
        if not _email_is_allowed(match.group(0)):
            return True
    return False


def _host_is_allowed(host: str) -> bool:
    normalized = host.strip().rstrip(".").casefold()
    if not normalized:
        return False
    if any(char in normalized for char in "{}$"):
        return True
    if ":" in normalized and normalized.count(":") == 1:
        normalized = normalized.rsplit(":", 1)[0]
    if normalized in ALLOWED_PUBLIC_HOSTS:
        return True
    return any(
        normalized == suffix[1:] or normalized.endswith(suffix)
        for suffix in _RESERVED_HOST_SUFFIXES
    )


def _network_privacy_hits(text: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for match in ABSOLUTE_URL_RE.finditer(text):
        token = match.group(0).rstrip(".,;:)")
        try:
            host = urlsplit(token).hostname or ""
        except ValueError:
            host = ""
        if not _host_is_allowed(host):
            hits.append(("unapproved absolute URL host", token))
    for match in HOST_FIELD_RE.finditer(text):
        host = match.group("host")
        if not _host_is_allowed(host):
            hits.append(("unapproved host-valued field", host))
    return hits


def _plan_historical_lines(lines: list[str]) -> list[bool]:
    historical_heading_level: int | None = None
    historical: list[bool] = []
    fence_char: str | None = None
    fence_length = 0

    def apply_heading(level: int, title: str) -> None:
        nonlocal historical_heading_level
        if title.strip().casefold() in PLAN_APPEND_ONLY_HEADINGS:
            if historical_heading_level is None or level <= historical_heading_level:
                historical_heading_level = level
        elif historical_heading_level is not None and level <= historical_heading_level:
            historical_heading_level = None

    for index, line in enumerate(lines):
        if fence_char is not None:
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)
            closing = re.fullmatch(
                rf"{re.escape(fence_char)}{{{fence_length},}}[ \t]*",
                stripped,
            )
            if indent <= 3 and closing:
                fence_char = None
                fence_length = 0
            historical.append(historical_heading_level is not None)
            continue

        fence = MARKDOWN_FENCE_RE.match(line)
        if fence:
            marker = fence.group("fence")
            fence_char = marker[0]
            fence_length = len(marker)
            historical.append(historical_heading_level is not None)
            continue

        setext = MARKDOWN_SETEXT_RE.match(line)
        if setext and index > 0 and lines[index - 1].strip():
            level = 1 if setext.group("marks").startswith("=") else 2
            apply_heading(level, lines[index - 1])
            historical[-1] = historical_heading_level is not None
            historical.append(historical_heading_level is not None)
            continue

        heading = MARKDOWN_HEADING_RE.match(line)
        if heading:
            level = len(heading.group("marks"))
            apply_heading(level, heading.group("title"))
        historical.append(historical_heading_level is not None)
    return historical


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
        payload = path.read_bytes()
    else:
        rel = path.relative_to(repo_root).as_posix()
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "show", f":{rel}"],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise OSError(f"cannot read staged content for {rel}")
        payload = proc.stdout

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        # Binary files are not exempt. Latin-1 is a one-byte-to-one-codepoint
        # mapping, so every source byte remains available to the ASCII privacy
        # and hygiene regexes without lossy replacement or an external tool.
        text = payload.decode("latin-1")
    return text.splitlines()


def run_gate(repo_root: Path, *, tracked_only: bool = False) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    errors: list[str] = []
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
        if rel in REMOVED_ARTIFACT_PATHS or any(
            prefix == rel or prefix in rel.parents for prefix in REMOVED_ARTIFACT_PREFIXES
        ):
            matches.append(
                {
                    "file": str(rel),
                    "line": 0,
                    "pattern": "removed purist artifact path",
                    "text": str(rel),
                }
            )
        # this loop only ever checked file *content*
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
            if _privacy_hits(label, pattern, rel_str):
                matches.append(
                    {
                        "file": rel_str,
                        "line": 0,
                        "pattern": f"{label} (in filename)",
                        "text": rel_str,
                    }
                )
        for label, token in _network_privacy_hits(rel_str):
            matches.append(
                {
                    "file": rel_str,
                    "line": 0,
                    "pattern": f"{label} (in filename)",
                    "text": token,
                }
            )
        try:
            lines = _read_scanned_lines(path, repo_root, tracked_only=tracked_only)
        except OSError as exc:
            errors.append(f"{rel}: cannot scan content: {exc}")
            continue
        plan_history = _plan_historical_lines(lines) if rel.name == "PLAN.md" else None
        for lineno, line in enumerate(lines, start=1):
            if plan_history is not None:
                historical = plan_history[lineno - 1]
            else:
                historical = _is_historical(rel)
            patterns = (
                PRIVACY_PATTERNS
                if historical or _hygiene_exempt(rel)
                else FORBIDDEN_PATTERNS
            )
            for label, pattern in patterns:
                if label in {item[0] for item in PRIVACY_PATTERNS}:
                    hit = _privacy_hits(label, pattern, line)
                else:
                    hit = pattern.search(line) is not None
                if hit:
                    matches.append(
                        {
                            "file": str(rel),
                            "line": lineno,
                            "pattern": label,
                            "text": line.strip(),
                        }
                    )
            for label, token in _network_privacy_hits(line):
                matches.append(
                    {
                        "file": str(rel),
                        "line": lineno,
                        "pattern": label,
                        "text": token,
                    }
                )

    return {
        "status": "failed" if matches or errors else "passed",
        "scope": "tracked" if tracked_only else "working-tree",
        "scanned_files": len(scanned_files),
        "matches": matches,
        "errors": errors,
    }


def run_metadata_gate(repo_root: Path, *, rev: str = "HEAD") -> dict[str, Any]:
    """Scan commit metadata that file-content scanning is structurally blind to.

    ``run_gate`` reads blobs (and now filenames) but never commit metadata, so
    it cannot see the two exposure classes that survive a clean tree:

    1. A foreign author/committer email renders a
       real, unrelated GitHub account as a public contributor. Enforced by
       ALLOWED_COMMIT_EMAILS: any identity not on the allowlist is a finding.
    2. A foreign ``Co-authored-by`` trailer email, which renders in the
       contributor sidebar exactly like an author. Enforced against the same
       allowlist.
    3. A privacy string in a commit message or trailer (e.g. a non-public
       email in a ``Co-authored-by`` trailer). PRIVACY_PATTERNS apply to every
       reachable commit's message body.

    HYGIENE_PATTERNS are intentionally *not* applied here: a retired term in an
    immutable historical commit message is the record, not a live surface.
    Findings are deduplicated (per identity; per pattern+line) so a leak
    repeated across N commits reports once with its commit count.
    """
    unit = "\x1f"
    proc = subprocess.run(
        [
            "git", "-C", str(repo_root), "log", rev, "-z",
            f"--format=%H{unit}%an{unit}%ae{unit}%cn{unit}%ce{unit}%B",
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "status": "failed",
            "scope": "commit-metadata",
            "scanned_commits": 0,
            "matches": [],
            "errors": [
                f"cannot read commit metadata for {rev!r}: "
                f"{proc.stderr.decode('utf-8', 'replace').strip()}"
            ],
        }

    bad_identities: dict[tuple[str, str, str], int] = {}
    message_hits: dict[tuple[str, str], dict[str, Any]] = {}
    scanned = 0
    for record in proc.stdout.split(b"\x00"):
        if not record:
            continue
        fields = record.split(unit.encode("utf-8"), 5)
        if len(fields) < 6:
            continue
        sha_b, an_b, ae_b, cn_b, ce_b, body_b = fields
        scanned += 1
        sha = sha_b.decode("utf-8", "replace")
        for role, name_b, email_b in (
            ("author", an_b, ae_b),
            ("committer", cn_b, ce_b),
        ):
            email = email_b.decode("utf-8", "replace")
            if not _commit_identity_allowed(email, commit_sha=sha, role=role):
                key = (role, name_b.decode("utf-8", "replace"), email)
                bad_identities[key] = bad_identities.get(key, 0) + 1
        body = body_b.decode("utf-8", "surrogateescape")
        for line in body.splitlines():
            trailer = CO_AUTHOR_TRAILER_RE.match(line)
            if trailer:
                trailer_email = trailer.group("email").strip()
                if not _commit_identity_allowed(
                    trailer_email,
                    commit_sha=sha,
                    role="co-author trailer",
                ):
                    key = ("co-author trailer", trailer.group("name"), trailer_email)
                    bad_identities[key] = bad_identities.get(key, 0) + 1
            for label, pattern in PRIVACY_PATTERNS:
                if _privacy_hits(label, pattern, line):
                    key = (label, line.strip())
                    hit = message_hits.setdefault(key, {"sha": sha, "count": 0})
                    hit["count"] += 1
            for label, token in _network_privacy_hits(line):
                key = (label, token)
                hit = message_hits.setdefault(key, {"sha": sha, "count": 0})
                hit["count"] += 1

    matches: list[dict[str, Any]] = []
    for (role, name, email), count in sorted(bad_identities.items()):
        plural = "" if count == 1 else "s"
        matches.append(
            {
                "file": "<commit-metadata>",
                "line": 0,
                "pattern": f"disallowed {role} identity",
                "text": f"{name} <{email}> ({count} commit{plural})",
            }
        )
    for (label, text), info in sorted(message_hits.items()):
        plural = "" if info["count"] == 1 else "s"
        matches.append(
            {
                "file": f"<commit-message {info['sha'][:12]}>",
                "line": 0,
                "pattern": label,
                "text": f"{text} ({info['count']} commit{plural})",
            }
        )

    return {
        "status": "failed" if matches else "passed",
        "scope": "commit-metadata",
        "scanned_commits": scanned,
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
    if "scanned_commits" in payload:
        lines.append(f"scanned_commits: {payload['scanned_commits']}")
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
    parser.add_argument(
        "--metadata",
        action="store_true",
        help=(
            "Also scan commit metadata (author/committer identity + message "
            "trailers) reachable from HEAD. Catches the foreign-contributor and "
            "trailer-leak classes that file-content scanning cannot see."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = run_gate(repo_root, tracked_only=args.tracked_only)
    if args.metadata:
        meta = run_metadata_gate(repo_root)
        payload["matches"] = payload["matches"] + meta["matches"]
        payload["scanned_commits"] = meta["scanned_commits"]
        payload["errors"] = payload["errors"] + meta["errors"]
        if meta["status"] == "failed":
            payload["status"] = "failed"
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_human(payload), end="")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
