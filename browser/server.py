#!/usr/bin/env python3
"""Small loopback briefing server for repository-owned Shadow plans."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
from typing import Any
from urllib.parse import urlparse
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    from board_projection import project_board_brief
    from chief_of_staff import project_chief_of_staff
    from decision_mode import DecisionInputError, build_choice, project_decision, receive_choice
    from outcome_source import OutcomeSourceError, project_plan_outcome
except ModuleNotFoundError:
    from browser.board_projection import project_board_brief
    from browser.chief_of_staff import project_chief_of_staff
    from browser.decision_mode import DecisionInputError, build_choice, project_decision, receive_choice
    from browser.outcome_source import OutcomeSourceError, project_plan_outcome
from shadow_scrub_lib import PRIVATE_PATH_RE as DRIVE_PRIVATE_PATH_RE
from shadow_scrub_lib import SECRET_SHAPE_RE as DRIVE_SECRET_SHAPE_RE
from shadow_root_board import (
    normalized_origin as _normalized_origin,
    origin_of as _origin_of,
    origin_repo_name as _origin_repo_name,
    plan_mtime as _plan_mtime,
)
import shadow_root_board as _root_board
import shadow_board_import as _board_import
import importlib.util as _ilu
_LINT_SPEC = _ilu.spec_from_file_location("shadow_lint", SCRIPTS / "shadow-lint.py")
shadow_lint = _ilu.module_from_spec(_LINT_SPEC)
_LINT_SPEC.loader.exec_module(shadow_lint)
_AMP_SPEC = _ilu.spec_from_file_location("shadow_browser_amp", SCRIPTS / "shadow-amp.py")
shadow_amp = _ilu.module_from_spec(_AMP_SPEC)
_AMP_SPEC.loader.exec_module(shadow_amp)


PRODUCT = "Shadow"
STATIC = Path(__file__).resolve().parent / "static"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()
MAX_REQUEST_BYTES = 16 * 1024
MAX_PLAN_BYTES = _root_board.MAX_PLAN_BYTES
MAX_PLANS = 250
SKIP_DIRS = frozenset({".git", ".shadow", ".venv", "venv", "node_modules", "dist", "build"})
FIELD_RE = re.compile(r"^\s*-\s*([^:]+):\s*(.*?)\s*$")
TASK_RE = re.compile(r"^\s*-\s*\[([^]]+)]\s*(.*?)\s*$")
RECEIPT_MARKER_RE = re.compile(r"\s*\[receipt:[a-f0-9]{16}]\s*")
# Title safety reuses the canonical private-path and secret-shape gates so the
# browser filter is never weaker than the evidence filters guarding this rail.
UNSAFE_TITLE_RE = re.compile(
    f"(?:{DRIVE_PRIVATE_PATH_RE.pattern}|{DRIVE_SECRET_SHAPE_RE.pattern})",
    re.IGNORECASE,
)
# Board fields are closed vocabularies or title-gated text, so a plan line can
# never carry a path or secret onto the board projection.
PROJECT_VALUE_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
# Grammar v2 has two postures. Legacy v1 modes are lint-blocking, so they
# never earn a chip; the board shows the finding instead.
MODE_VALUE_RE = re.compile(r"^(?:explore|ship)$")
CHECKPOINT_STATES = ("pending", "in_progress", "blocked", "completed")
CHECKPOINT_ALIASES = {"x": "completed", "done": "completed", "working": "in_progress"}
ALLOWED_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/gallery": ("gallery.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/gallery.js": ("gallery.js", "text/javascript; charset=utf-8"),
    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
    "/static/gallery.css": ("gallery.css", "text/css; charset=utf-8"),
}

DEV_ROOT = Path.home() / "Development"


class BrowserError(ValueError):
    pass


def root_id(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]


def public_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if len(slug) < 3:
        slug = f"project-{slug or 'work'}"
    return slug[:64]


def section(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    target = f"## {name}".lower()
    start = next((index + 1 for index, line in enumerate(lines) if line.strip().lower() == target), None)
    if start is None:
        return []
    result = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        result.append(line)
    return result


def operator_brief(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in section(text, "Brief"):
        match = FIELD_RE.match(line)
        if not match:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
        result[key] = match.group(2).strip()
    return result


def title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            clean = " ".join(line[2:].split())
            clean = re.sub(r"^[A-Za-z]+\d+\s*[—-]\s*", "", clean)
            if clean and UNSAFE_TITLE_RE.search(clean) is None:
                return clean[:120]
    return public_id(fallback).replace("-", " ").title()


def latest_progress(text: str) -> str | None:
    rows = [line.strip()[2:] for line in section(text, "Progress") if line.strip().startswith("- ")]
    if not rows:
        return None
    return RECEIPT_MARKER_RE.sub(" ", rows[-1]).strip()[:280]



def read_plan(path: Path) -> str:
    try:
        return _root_board.read_plan_text(path)
    except _root_board.BoardError as exc:
        raise BrowserError(str(exc)) from exc


def project_of(brief: dict[str, str], relative: str) -> str:
    raw = (brief.get("project") or "").strip().lower()
    if PROJECT_VALUE_RE.fullmatch(raw):
        return raw
    head = relative.split("/", 1)[0].lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", head).strip("-")[:32]
    return slug if PROJECT_VALUE_RE.fullmatch(slug) else "unassigned"


def mode_of(brief: dict[str, str]) -> str | None:
    raw = (brief.get("mode") or "").strip().lower()
    return raw if MODE_VALUE_RE.fullmatch(raw) else None


def milestone_of(brief: dict[str, str]) -> str | None:
    raw = " ".join((brief.get("milestone") or "").split())
    if not raw or UNSAFE_TITLE_RE.search(raw):
        return None
    return raw[:120]


def checkpoint_counts(text: str) -> dict[str, int] | None:
    lines = section(text, "Tasks")
    if not lines:
        return None
    counts = {state: 0 for state in CHECKPOINT_STATES}
    for line in lines:
        match = TASK_RE.match(line)
        if not match:
            continue
        state = match.group(1).strip().lower()
        state = CHECKPOINT_ALIASES.get(state, state)
        if state in counts:
            counts[state] += 1
    return counts


def lint_summary(text: str) -> dict[str, Any]:
    try:
        findings = shadow_lint.lint_plan(text)
    except Exception:
        return {"parse_ok": False, "blocking": 0, "warning": 0}
    return {
        "parse_ok": True,
        "blocking": sum(1 for f in findings if f["severity"] == "blocking"),
        "warning": sum(1 for f in findings if f["severity"] == "warning"),
    }


def plan_record(path: Path, root: Path) -> dict[str, Any]:
    text = read_plan(path)
    relative = path.relative_to(root).as_posix()
    return record_from_text(text, relative, path.parent.name)


def _board_payload(root: Path, home: Path) -> tuple[dict, str | None]:
    """Refresh bounded discovery, or keep serving the last good computer board."""
    from shadow_board_import import reconcile_portfolio

    try:
        return reconcile_portfolio(root, shadow_amp, home=home), None
    except _root_board.BoardError as exc:
        try:
            payload = _root_board.snapshot(home=home)
        except _root_board.BoardError as board_exc:
            raise BrowserError("this computer's root board is unreadable") from board_exc
        if payload is None:
            raise BrowserError(str(exc)) from exc
        return payload, str(exc)


def _rotation_text(value: str, fallback: str, limit: int = 220) -> str:
    clean = " ".join(value.split())
    if not clean or UNSAFE_TITLE_RE.search(clean):
        return fallback
    return clean[:limit]


def _milestone_rotation(
    parsed: dict,
    resume_id: str | None,
    claims: list[dict],
) -> list[dict[str, Any]]:
    """Project every live milestone from the already parsed canonical plan."""
    owners: dict[str, list[str]] = {}
    for claim in claims:
        owners.setdefault(claim["row"], []).append(claim["owner"])
    parsed["claimed"] = set(owners)
    reachable = set(shadow_amp._candidate_ids(parsed))
    rotation: list[dict[str, Any]] = []
    for milestone in parsed["milestones"]:
        checkpoints = []
        for row in milestone["rows"]:
            row_owners = sorted(set(owners.get(row["id"], [])))
            is_resume = row["id"] == resume_id
            if row["state"] == "completed" and not row_owners and not is_resume:
                continue
            checkpoints.append(
                {
                    "id": row["id"],
                    "state": row["state"],
                    "text": _rotation_text(row["text"], "Checkpoint text withheld"),
                    "availability": (
                        "claimed" if row_owners else
                        "blocked" if row["state"] == "blocked" else
                        "reachable" if row["id"] in reachable else
                        "waiting"
                    ),
                    "resume": is_resume,
                    "owners": row_owners,
                }
            )
        if not any(row["state"] != "completed" for row in milestone["rows"]) and not checkpoints:
            continue
        counts = {
            state: sum(1 for row in milestone["rows"] if row["state"] == state)
            for state in CHECKPOINT_STATES
        }
        rotation.append(
            {
                "title": _rotation_text(
                    re.sub(r"^[A-Za-z]+\d+\s*[—-]\s*", "", milestone["title"]),
                    "Milestone",
                ),
                "counts": counts,
                "current": any(row["resume"] for row in checkpoints),
                "resume": next(
                    (row["id"] for row in checkpoints if row["resume"]), None
                ),
                "owners": sorted(
                    {owner for row in checkpoints for owner in row["owners"]}
                ),
                "checkpoints": checkpoints,
            }
        )
    return rotation


def _board_plan_record(
    payload: dict,
    entity: dict,
    priorities: dict[str, int],
) -> dict[str, Any]:
    """Project one canonical entity pointer without making its locator authority."""
    plan = Path(entity["plan"])
    locator = _root_board.public_plan_locator(plan)
    text = ""
    parsed = None
    try:
        if not _root_board.regular_plan(plan):
            raise BrowserError("registered entity plan is missing, unreadable, or a symlink")
        text = read_plan(plan)
        parsed = shadow_amp._parse(text)
        record = record_from_text(text, locator, entity["project"])
    except (BrowserError, OSError, UnicodeError, ValueError):
        record = record_from_text("", locator, entity["project"])
        record["contract_error"] = "The registered entity plan is missing or unreadable."
        record["broken"] = True
        record["board"]["state"] = "broken"
    claims = [
        claim for claim in payload["claims"] if claim["entity"] == entity["id"]
    ]
    record.update(
        {
            "id": entity["id"],
            "entity": entity["id"],
            "project": entity["project"],
            "path": locator,
            "priority": priorities[entity["project"]],
            "resume": entity["resume"],
            "root_board_revision": payload["revision"],
            "claims": [
                {
                    "row": claim["row"],
                    "owner": claim["owner"],
                    "return_by": claim["return_by"],
                }
                for claim in claims
            ],
        }
    )
    record["milestones"] = (
        _milestone_rotation(parsed, entity["resume"], claims)
        if parsed is not None else []
    )
    record["board"]["priority"] = str(priorities[entity["project"]])
    active = next(
        (claim for claim in claims if claim["row"] == entity["resume"]),
        claims[0] if claims else None,
    )
    if active is not None and parsed is not None:
        located = next(
            (
                (milestone, row)
                for milestone in parsed["milestones"]
                for row in milestone["rows"]
                if row["id"] == active["row"]
            ),
            None,
        )
        record["board"]["state"] = "working"
        record["owner"] = active["owner"]
        if located is not None:
            milestone, row = located
            shown = record["board"].get("milestone") or {
                "title": milestone["title"],
                "counts": {state: 0 for state in CHECKPOINT_STATES},
                "current": None,
                "next": None,
                "dod": None,
            }
            shown["title"] = milestone["title"]
            shown["current"] = row["text"]
            record["board"]["milestone"] = shown
    if parsed is not None:
        row_ids = {
            row["id"]
            for milestone in parsed["milestones"]
            for row in milestone["rows"]
        }
        issue = _root_board.entity_integrity(
            entity,
            claims,
            row_ids,
            shadow_amp._candidate_ids(parsed),
        )
        if issue:
            record["broken"] = True
            record["contract_error"] = issue
            record["board"]["state"] = "broken"
    return record


def board_plan_records(root: Path, home: Path) -> tuple[dict, list[dict[str, Any]], str | None]:
    payload, warning = _board_payload(root, home)
    priorities = {project["id"]: project["priority"] for project in payload["projects"]}
    ordered = sorted(
        payload["entities"],
        key=lambda entity: (priorities[entity["project"]], entity["project"], entity["id"]),
    )
    records = [
        _board_plan_record(payload, entity, priorities) for entity in ordered
    ]
    broken = sum(1 for record in records if record.get("broken"))
    if broken:
        warning = warning or f"{broken} computer-board entity pointer(s) are broken"
    return payload, records, warning


def board_entity_plan(identity: Any, revision: Any, home: Path) -> Path:
    if not isinstance(identity, str) or _root_board.ENTITY_ID.fullmatch(identity) is None:
        raise BrowserError("entity id is required")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise BrowserError("root board revision is required")
    try:
        return _root_board.canonical_plan_by_id_at_revision(
            identity,
            revision=revision,
            home=home,
        )
    except _root_board.BoardError as exc:
        raise BrowserError(str(exc)) from exc


def record_from_text(text: str, relative: str, title_fallback: str) -> dict[str, Any]:
    """One projection pipeline for real plans and gallery fixtures alike.

    The gallery exists to show every card state from checked-in fixture plan
    TEXTS run through THIS function — precomputed briefs would drift from the
    projection the moment either changed."""
    brief = operator_brief(text)
    outcome = None
    decision = None
    chief = None
    error = None
    # The v4 board brief is TOTAL — every readable plan gets one. The v3
    # typed-Outcome contract is attempted only for a plan that still carries
    # its keys; its absence is the current grammar, not an error. Before this
    # split, every v4 plan on a machine failed "outcome must be a string" and
    # the board rendered nothing it existed to show.
    board = project_board_brief(text)
    if "outcome" in brief:
        try:
            outcome = project_plan_outcome(brief)
            decision = project_decision(outcome)
            plan_summary = {"latest_change": latest_progress(text)} if latest_progress(text) else None
            chief = project_chief_of_staff(outcome, plan_brief=plan_summary)
        except (OutcomeSourceError, DecisionInputError) as exc:
            error = str(exc)
    return {
        "id": hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16],
        "path": relative,
        "title": title(text, title_fallback),
        "project": project_of(brief, relative),
        "mode": mode_of(brief),
        "milestone": milestone_of(brief),
        "tasks": checkpoint_counts(text),
        "lint": lint_summary(text),
        "outcome": outcome,
        "decision": decision,
        "briefing": chief,
        "board": board,
        "contract_error": error,
    }


GALLERY_FIXTURES = STATIC / "gallery-fixtures.json"


def gallery_records() -> list[dict[str, Any]]:
    """Every card state, from checked-in fixture plan texts, projected by the
    SAME pipeline real plans use. The fixture file names the state each text
    must project to; a test holds that promise so the gallery cannot lie."""
    import json as _json

    entries = _json.loads(GALLERY_FIXTURES.read_text(encoding="utf-8"))
    records = []
    for name, entry in entries.items():
        record = record_from_text(entry["plan"], f"gallery/{name}", name)
        record["title"] = entry["label"]
        record["gallery_name"] = name
        record["expected_state"] = entry["expected_state"]
        records.append(record)
    return records
# A plan demoting ITSELF, not prose about archiving. "docs/plan-archive/" and
# "archive the milestone" appear in every healthy plan, so the marker has to be
# a self-verdict: the words a person writes when they mean "stop working this
# file". Matched case-insensitively over the first lines only, where a banner
# lives — a phrase quoted deep in Progress is a record, not a verdict.
#
# The demotion phrase alone is not enough either. A live plan can open with
# "do not revive the old service" or call a component "a historical shell":
# true sentences about something else. So the phrase only counts when it is
# bound, inside one sentence, to a subject naming THIS plan — the difference
# between describing an archive and being one.
#
# The qualifiers between "this" and the noun are a closed list, not any word:
# "this deployment plan" or "this rollout plan" names a plan of work, and a row
# saying "do not update this deployment plan yet" is scheduling, not a verdict.
# Only a phrase that can mean the file being read counts.
_VETO_SELF = (
    r"this\s+(?:root\s+|top-level\s+|entire\s+|whole\s+|repo(?:sitory)?\s+"
    r"|milestone\s+|shadow\s+)*(?:plan(?:\.md)?|file|document)\b"
)
_VETO_DEMOTION = (
    r"non-executable(?:\s+archive)?(?:\s+shell)?|archive shell|historical shell"
    r"|do not revive|do not update"
)
ARCHIVE_VETO_RE = re.compile(
    rf"(?:{_VETO_SELF})[^.\n]{{0,80}}?(?:{_VETO_DEMOTION})"
    rf"|(?:{_VETO_DEMOTION})[^.\n]{{0,80}}?(?:{_VETO_SELF})",
    re.IGNORECASE,
)
VETO_SCAN_LINES = 40
PUBLIC_ARCHIVE_VETO = "non-executable archive shell"


def _archive_veto_text(text: str) -> str | None:
    """Return the matched self-demotion from one already frozen plan snapshot."""
    head = "\n".join(text.splitlines()[:VETO_SCAN_LINES])
    found = ARCHIVE_VETO_RE.search(head)
    return found.group(0) if found else None


def _archive_veto_receipt(paths: list[Path]) -> dict[str, Any] | None:
    """Freeze the exact source whose self-demotion retires a logical plan."""
    for candidate in paths:
        state, content = _root_board.plan_state_snapshot(candidate)
        if content is None:
            continue
        # The veto is deliberately a first-lines verdict. A malformed or
        # oversized tail cannot revive a file whose bounded ASCII head has
        # already demoted the whole plan; the state token still CASes the
        # complete bounded snapshot and file metadata before retirement.
        text = content[:65_536].decode("utf-8", errors="ignore")
        found = _archive_veto_text(text)
        if found:
            return {
                "match": found,
                "plan": str(candidate.resolve()),
                "expected_state": state,
            }
    return None


def _archive_veto(paths: list[Path]) -> str | None:
    """The self-demotion found on ANY instance of one logical plan.

    Guarded exactly as `read_plan` guards the record it builds. A repo's root
    `PLAN.md` is admitted on `is_file()`, which a symlink satisfies, so a
    sibling checkout could point its plan anywhere on the filesystem and have
    that content decide whether the logical plan is authority. The reader that
    demotes must be no more permissive than the reader that renders.
    """
    receipt = _archive_veto_receipt(paths)
    return receipt["match"] if receipt else None
MAX_DECLARED_GLOBS = 3


def declared_plan_globs(plan_text: str) -> list[str]:
    """The repo-relative globs a root plan declares, bounded and sanitized.

    Read from the Brief and nowhere else, like every other operator field. The
    grammar calls this "one Brief line"; scanning the whole document would let
    a `- Plans:` line quoted in Progress, a note, or a fenced example become an
    authoritative declaration that widens what the board reads.

    Repo-relative only. An absolute path or a `..` segment would let one
    repository's plan pull files from outside itself into the board — the same
    class of reach a central index would have, arriving one line at a time.
    """
    declaration = operator_brief(plan_text).get("plans")
    if not declaration:
        return []
    globs: list[str] = []
    for raw in declaration.split(","):
        candidate = raw.strip()
        if not candidate or candidate.startswith("/") or ".." in Path(candidate).parts:
            continue
        if "**" in Path(candidate).parts:
            raise BrowserError(
                "recursive plan globs are not supported; declare bounded depths explicitly"
            )
        globs.append(candidate)
        if len(globs) == MAX_DECLARED_GLOBS:
            break
    return globs


def repo_plans(repo: Path, *, declaration_plan: Path | None = None) -> list[Path]:
    """This root's own plan, plus anything that plan declares."""
    root_plan = repo / "PLAN.md"
    if not (root_plan.exists() or root_plan.is_symlink()):
        return []
    found = {root_plan}
    try:
        # A uniquely healthy registered root is already the computer's
        # authority. Its declaration, not a stale sibling's, decides which
        # nested shards that sibling may contribute to bounded discovery.
        text = read_plan(declaration_plan or root_plan)
    except (BrowserError, OSError, UnicodeError):
        return [root_plan]
    # BOTH sides resolved. Comparing an unresolved repo against resolved
    # parents never matches on macOS, where /var is a symlink to /private/var —
    # which silently excluded every declared plan while looking like a working
    # containment check.
    here = repo.resolve()
    for pattern in declared_plan_globs(text):
        for path in repo.glob(pattern):
            # A glob that escapes through a symlink is the one way a
            # repo-relative pattern still reaches outside its own repo.
            if path in found or path.name != "PLAN.md":
                continue
            if path.is_symlink():
                found.add(path)
                continue
            try:
                contained = here in path.resolve().parents
            except OSError:
                contained = False
            if not contained or not path.exists():
                continue
            if _pruned_segment(path.relative_to(repo)):
                continue
            found.add(path)
            if len(found) > MAX_PLANS:
                raise BrowserError(
                    f"one repository declares more than {MAX_PLANS} plans; split its bounded shards"
                )
    return [root_plan, *sorted(found - {root_plan})]


def _pruned_segment(relative: Path) -> str | None:
    """The directory that disqualifies a declared-glob hit, if any.

    `Path.glob` descends into dot-directories, so a single declared
    `**/PLAN.md` reached into `.worktrees/`, `node_modules/`, and every
    vendored copy — putting a worktree pool and a dependency's template plan
    on the board as if they were projects. `SKIP_DIRS` already named exactly
    these directories and had no readers at all; this makes it load-bearing
    rather than adding a second list to drift from it.

    Only the declared-glob expansion is filtered. A repo's own root plan is
    never subject to this, and the portfolio walk prunes hidden children of
    its own accord.
    """
    for segment in relative.parts[:-1]:
        if segment in SKIP_DIRS or segment.startswith("."):
            return segment
    return None


def is_repo(path: Path) -> bool:
    # A worktree's .git is a FILE pointing at the real one; both are repos.
    return (path / ".git").exists()


def is_plan_root(path: Path) -> bool:
    """A directory that owns a plan.

    Deliberately NOT "is a git repository". The point of enumerating roots
    instead of walking directories is boundedness — no recursion, no cap, no
    reading outside the portfolio. Requiring git on top of that would make a
    plan in a plain directory invisible, which is a restriction nobody asked
    for. Git identity is used for deduplication when it is there, and the path
    stands in when it is not.
    """
    plan = path / "PLAN.md"
    return plan.exists() or plan.is_symlink()


def is_portfolio_child(child: Path, root: Path) -> bool:
    """True when `child` really lives directly inside the resolved portfolio.

    A symlinked entry passes `is_dir()` and owns a `PLAN.md` while pointing
    anywhere on the filesystem; resolving it is what keeps the board from
    reading plans the portfolio does not contain.
    """
    try:
        return child.resolve().parent == root
    except OSError:
        return False


def discover_plans(
    root: Path,
    *,
    include_shadowed: bool = False,
    fail_on_skipped: bool = False,
    registered_plans: dict[str, Path] | None = None,
    repairable_plans: dict[str, Path] | None = None,
    retired_registered: set[str] | None = None,
    capture_tokens: bool = False,
) -> list[dict[str, Any]]:
    """Every plan the portfolio can legally see.

    Repositories are enumerated, never directories. A recursive walk reached
    777 files on the reference machine, 665 of them byte-identical copies, and
    filled its 250-slot cap alphabetically — silently dropping Shadow's own
    plan and every repository sorting after `resplit-`. It also had no
    boundary: only the fact that `Development` sorts before `Documents` kept it
    from rendering session directories whose names are prompt text.
    """
    records: list[dict[str, Any]] = []
    shadowed: list[dict[str, Any]] = []
    registered = {
        identity: Path(path).resolve()
        for identity, path in (registered_plans or {}).items()
    }
    repairable = {
        identity: Path(os.path.abspath(path))
        for identity, path in (repairable_plans or {}).items()
    }
    # key -> the root-relative path that won it, so a suppressed record can
    # name its winner instead of just vanishing.
    seen: dict[tuple[str, str], str] = {}
    if is_plan_root(root):
        candidates = [root]
    elif root.is_dir():
        try:
            children = list(root.iterdir())
        except OSError as exc:
            if fail_on_skipped:
                raise BrowserError("portfolio root cannot be enumerated") from exc
            children = []
        # BOTH sides resolved, for the same reason the declared globs are:
        # a symlinked child resolves somewhere else entirely, and following it
        # would read a plan from outside the portfolio — the one boundary this
        # enumeration exists to keep.
        here = root.resolve()
        found = [
            child for child in children
            if child.is_dir() and not child.name.startswith(".")
            and is_portfolio_child(child, here) and is_plan_root(child)
        ]
        # Order decides which checkout of a shared origin wins deduplication,
        # so it cannot be plain alphabetical. A rename-era clone of a repository
        # keeps its old directory name, which may sort first and silently
        # replace the canonical checkout's plan with a stale copy — observed on
        # the reference machine against this very repository. Prefer the
        # checkout whose directory name matches the origin's repository name,
        # then the one whose plan was touched most recently. The comparison is
        # case-folded on both sides: the normalized origin is lowercased, so a
        # `Thing` directory cloned from `.../thing` would otherwise lose the
        # tie-break to whatever mtime and alphabetical order happened to pick.
        candidates = sorted(
            found,
            key=lambda repo: (
                repo.name.lower() != _origin_repo_name(_origin_of(repo)).lower(),
                -_plan_mtime(repo),
                repo.name,
            ),
        )
    else:
        candidates = []
    # Every instance of every key, gathered BEFORE election. A plan's own
    # demotion can sit on a copy no rule elects — measured on this machine,
    # where resplit-ios/PLAN.md wins on every structural rule while the
    # "non-executable archive shell, do not revive" banner exists only on the
    # unelected divergent copy at resplit-ios-deploy-watcher. Reading just the
    # winner cannot see that, so the verdict is sought across the whole key,
    # which is already enumerated here.
    plans_by_repo: dict[Path, list[Path]] = {}
    identities: dict[Path, tuple[str, Path]] = {}
    for repo in candidates:
        origin, root_relative = _root_board.plan_identity_parts(repo / "PLAN.md")
        prefix = Path(root_relative).parent
        identities[repo] = (origin, prefix)
        root_identity = _root_board.logical_entity_id(origin, root_relative)
        if root_identity in (retired_registered or set()):
            plans_by_repo[repo] = [repo / "PLAN.md"]
        else:
            plans_by_repo[repo] = repo_plans(
                repo,
                declaration_plan=registered.get(root_identity),
            )

    instances: dict[tuple[str, str], list[Path]] = {}
    for repo in candidates:
        origin, prefix = identities[repo]
        for path in plans_by_repo[repo]:
            logical_relative = (prefix / path.relative_to(repo)).as_posix()
            instances.setdefault(
                (origin, logical_relative), []).append(path)

    for repo in candidates:
        origin, prefix = identities[repo]
        for path in plans_by_repo[repo]:
            relative = path.relative_to(repo)
            key = (origin, (prefix / relative).as_posix())
            identity = _root_board.logical_entity_id(*key)
            registered_plan = registered.get(identity)
            repairable_plan = repairable.get(identity)
            candidate_plan = Path(os.path.abspath(path))
            alternatives = instances.get(key, [])
            if (
                repairable_plan is not None
                and candidate_plan == repairable_plan
                and any(Path(os.path.abspath(item)) != repairable_plan for item in alternatives)
            ):
                # A broken registered checkout is the state being repaired, not
                # the authority that may prevent a healthy same-identity sibling
                # from entering the repair transaction. With no alternative it
                # remains a strict import failure and the last-good board stays red.
                continue
            registered_retirement = identity in (retired_registered or set())
            registered_override = (
                registered_plan
                if registered_plan is not None
                and Path(os.path.abspath(path)) != registered_plan
                else None
            )
            veto_receipt = None
            veto = None
            if registered_override is not None and not registered_retirement:
                veto_paths = list(instances.get(key, [path]))
                if registered_plan not in veto_paths:
                    veto_paths.append(registered_plan)
                veto_receipt = _archive_veto_receipt(veto_paths)
                veto = veto_receipt["match"] if veto_receipt else None
            # Deduplicate before reading. A broken ghost checkout must not veto
            # the healthy canonical copy that already won this logical key.
            if key in seen and not include_shadowed:
                continue
            if len(seen) >= MAX_PLANS:
                raise BrowserError(
                    f"portfolio exposes more than {MAX_PLANS} logical plans; "
                    "close, archive, or split the import scope"
                )
            try:
                if registered_retirement:
                    display = path.relative_to(root).as_posix()
                    record = {
                        "path": display,
                        "archived": True,
                        "archive_veto": PUBLIC_ARCHIVE_VETO,
                    }
                    if capture_tokens:
                        record["_logical_entity"] = identity
                elif registered_override is not None:
                    display = path.relative_to(root).as_posix()
                    if veto:
                        record = {
                            "path": display,
                            "archived": True,
                            "archive_veto": PUBLIC_ARCHIVE_VETO,
                        }
                    else:
                        record = record_from_text(
                            read_plan(registered_override),
                            display,
                            path.parent.name,
                        )
                    # Internal only. Import turns it into a canonical seed and
                    # inspection turns it into a public suppression receipt.
                    if capture_tokens:
                        record["_registered_pointer"] = True
                        record["_logical_entity"] = identity
                else:
                    record = plan_record(path, root)
            except (BrowserError, OSError, UnicodeError, ValueError) as exc:
                if fail_on_skipped:
                    reason = (
                        str(exc)
                        if isinstance(exc, BrowserError)
                        else "plan is unreadable, invalid UTF-8, or malformed"
                    )
                    try:
                        display = path.relative_to(root).as_posix()
                    except ValueError:
                        display = relative.as_posix()
                    raise BrowserError(f"{display}: {reason}") from exc
                continue
            if capture_tokens:
                record.setdefault("_logical_entity", identity)
            # One logical plan per (origin, repo-relative path): a worktree or
            # clone is the same plan as its main checkout, not a second card.
            if key in seen:
                # Suppression is a real answer, and a reader who cannot see it
                # has no way to tell "identical copy dropped" from "a plan I
                # needed went missing". The record is already built above, so
                # surfacing it costs a field, not a second parse.
                if include_shadowed:
                    record["shadowed_by"] = seen[key]
                    record["shadow_reason"] = f"same repository as {seen[key]}"
                    shadowed.append(record)
                continue
            seen[key] = record["path"]
            if registered_override is None:
                veto_receipt = _archive_veto_receipt(instances.get(key, [path]))
                veto = veto_receipt["match"] if veto_receipt else None
            if veto:
                record["archived"] = True
                record["archive_veto"] = PUBLIC_ARCHIVE_VETO
                assert veto_receipt is not None
                if capture_tokens:
                    record["_retired_plan"] = veto_receipt["plan"]
                    record["_retired_state"] = veto_receipt["expected_state"]
            records.append(record)
    rank = {"needs_you": 0, "blocked": 1, "working": 2, "not_delivered": 3, "finished_with_proof": 4}
    records.sort(
        key=lambda item: (
            rank.get((item.get("briefing") or {}).get("state"), 5),
            item.get("title", "").lower(),
            item["path"],
        )
    )
    # Shadowed rows sort after every rendered one, by reason then path, so the
    # extra view is a stable append rather than a reshuffle of the board.
    shadowed.sort(key=lambda item: (item["shadow_reason"], item["path"]))
    return records + shadowed


def is_live(record: dict[str, Any]) -> bool:
    """Whether one record may be presented as authority.

    The rule lives here, in one place, because it now has more than one caller:
    the browser wire and `shadow status`. A second surface re-spelling
    `not record["archived"]` is how the two drift back apart.
    """
    return not record.get("archived")


def live_plans(root: Path, *, fail_on_skipped: bool = False) -> list[dict[str, Any]]:
    """What the board is allowed to render as authority.

    Annotating a demoted record is not a demotion: the projections iterate the
    served list and never read `archived`, so a vetoed archive shell would keep
    its card, its live briefing and its decision buttons. The one place that
    cannot be forgotten is the wire — a record the browser never receives
    cannot render as authority in any view, present or future.
    """
    return [
        record
        for record in discover_plans(root, fail_on_skipped=fail_on_skipped)
        if is_live(record)
    ]


def resolve_plan(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise BrowserError("plan path is required")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise BrowserError("plan path must be relative")
    root = root.resolve()
    candidate = root
    for part in relative.parts:
        candidate /= part
        if candidate.is_symlink():
            raise BrowserError("plan path must not contain symlinks")
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BrowserError("plan path escapes the scan root") from exc
    if candidate.name != "PLAN.md":
        raise BrowserError("plan path must name PLAN.md")
    read_plan(candidate)
    return candidate


def repository_root(plan: Path) -> Path:
    plan = plan.resolve()
    result = subprocess.run(
        ["git", "-C", str(plan.parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise BrowserError("plan is not inside a Git worktree")
    repo = Path(result.stdout.strip()).resolve()
    try:
        plan.relative_to(repo)
    except ValueError as exc:
        raise BrowserError("plan escapes its Git worktree") from exc
    return repo



def write_decision_receipt(plan: Path, document: dict[str, Any], option_id: Any, revision: Any) -> dict[str, Any]:
    plan = plan.resolve()
    if isinstance(revision, bool) or not isinstance(revision, int):
        raise BrowserError("revision must be an integer")
    choice = build_choice(document, option_id)
    choice["revision"] = revision
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = receive_choice(document, choice, updated_at=now)
    repo = repository_root(plan)
    relative_plan = plan.relative_to(repo).as_posix()
    core = {
        "schema": "shadow.local-decision.v1",
        "plan": relative_plan,
        "outcome_id": result["receipt"]["outcome_id"],
        "decision_id": result["receipt"]["ask_id"],
        "option_id": result["receipt"]["option_id"],
        "observed_revision": result["receipt"]["observed_revision"],
        "authority_revision": result["receipt"]["authority_revision"],
        "state": result["receipt"]["state"],
        "reason": result["receipt"]["reason"],
    }
    encoded_core = json.dumps(core, sort_keys=True, separators=(",", ":"))
    identifier = hashlib.sha256(encoded_core.encode("utf-8")).hexdigest()[:16]
    payload = {**core, "receipt_id": identifier, "recorded_at": now}
    directory = repo / ".shadow" / "evidence"
    if (repo / ".shadow").is_symlink() or directory.is_symlink():
        raise BrowserError("evidence path must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"decision-{identifier}.json"
    if destination.is_symlink():
        raise BrowserError("decision receipt must not be a symlink")
    if destination.exists():
        current = json.loads(destination.read_text(encoding="utf-8"))
        if current.get("receipt_id") != identifier:
            raise BrowserError("decision receipt collision")
        return current
    fd, temporary = tempfile.mkstemp(prefix=".decision.", dir=directory)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError:
            current = json.loads(destination.read_text(encoding="utf-8"))
            if current.get("receipt_id") != identifier:
                raise BrowserError("decision receipt collision")
            return current
    finally:
        temporary_path.unlink(missing_ok=True)
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "Shadow/1"

    @property
    def scan_root(self) -> Path:
        return self.server.scan_root  # type: ignore[attr-defined]

    @property
    def board_home(self) -> Path:
        return self.server.board_home  # type: ignore[attr-defined]

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()

    def _send(self, status: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
        self._headers(status, content_type, len(body))
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, (json.dumps(value, sort_keys=True) + "\n").encode("utf-8"), "application/json")

    def _loopback(self) -> bool:
        return self.client_address[0] in {"127.0.0.1", "::1"}

    def _valid_host(self) -> bool:
        raw = self.headers.get("Host")
        if not raw:
            return False
        try:
            parsed = urlparse(f"//{raw}")
            port = parsed.port
        except ValueError:
            return False
        hostname = (parsed.hostname or "").lower()
        if hostname in {"127.0.0.1", "localhost", "::1"}:
            return port == self.server.server_address[1]
        # An allow-listed proxy hostname owns its own outer port.
        return hostname in self.server.extra_hosts

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return False
        parsed = urlparse(origin)
        host = (parsed.hostname or "").lower()
        if parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}:
            return parsed.port == self.server.server_address[1]
        return parsed.scheme == "https" and host in self.server.extra_hosts

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        if not self._loopback() or not self._valid_host():
            self._json(403, {"error": "loopback Host required"})
            return
        parsed = urlparse(self.path)
        if parsed.path in ALLOWED_STATIC:
            name, content_type = ALLOWED_STATIC[parsed.path]
            self._send(200, (STATIC / name).read_bytes(), content_type)
            return
        if parsed.path == "/api/health":
            self._json(
                200,
                {
                    "ok": True,
                    "product": PRODUCT,
                    "version": VERSION,
                    "root_id": root_id(self.scan_root),
                    "server_mtime_ns": Path(__file__).stat().st_mtime_ns,
                },
            )
            return
        if parsed.path == "/api/plans":
            try:
                payload, plans, warning = board_plan_records(self.scan_root, self.board_home)
                self._json(
                    200,
                    {
                        "product": PRODUCT,
                        "root_board_revision": payload["revision"],
                        "plans": plans,
                        "warning": warning,
                    },
                )
            except BrowserError as exc:
                self._json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/gallery":
            self._json(200, {"product": PRODUCT, "plans": gallery_records()})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        endpoint = urlparse(self.path).path
        if endpoint != "/api/decision":
            self._json(404, {"error": "not found"})
            return
        if not self._loopback() or not self._valid_host() or not self._same_origin():
            self._json(403, {"error": "local changes require this loopback browser"})
            return
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"error": "application/json required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_REQUEST_BYTES:
            self._json(413, {"error": "request exceeds the bounded limit"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or set(payload) != {
                "entity", "root_board_revision", "option_id", "revision"
            }:
                raise BrowserError("decision request has unknown or missing fields")
            refreshed, warning = _board_payload(self.scan_root, self.board_home)
            if warning is not None:
                raise BrowserError(
                    "computer board refresh failed; resolve the displayed warning and reload"
                )
            if refreshed["revision"] != payload["root_board_revision"]:
                raise BrowserError("root board changed; refresh before writing")
            try:
                with _root_board.locked_entity_plan_by_id_at_revision(
                    payload["entity"],
                    revision=payload["root_board_revision"],
                    home=self.board_home,
                ) as plan:
                    record = record_from_text(
                        read_plan(plan),
                        _root_board.public_plan_locator(plan),
                        plan.parent.name,
                    )
                    if record["outcome"] is None:
                        raise BrowserError(
                            record["contract_error"] or "plan has no typed Outcome"
                        )
                    receipt = write_decision_receipt(
                        plan,
                        record["outcome"],
                        payload["option_id"],
                        payload["revision"],
                    )
            except _root_board.BoardError as exc:
                raise BrowserError(str(exc)) from exc
            self._json(200, {"ok": True, "receipt": receipt})
        except (BrowserError, DecisionInputError) as exc:
            self._json(400, {"error": str(exc)})
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Never reflect raw exception text: an OSError carries the full
            # absolute path, and the browser must never receive paths.
            self._json(
                400,
                {"error": "Shadow could not read or update that plan on this computer."},
            )

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("SHADOW_BROWSER_QUIET") != "1":
            super().log_message(format, *args)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        root: Path,
        extra_hosts: frozenset[str] = frozenset(),
        *,
        home: Path | None = None,
    ) -> None:
        super().__init__(address, Handler)
        self.scan_root = root.resolve()
        # Tests and embedded callers default to an isolated root-owned home;
        # the production entrypoint passes the real user home explicitly.
        self.board_home = (home or root).resolve()
        # Opt-in Host-header allowlist for a proxy the operator runs on this
        # machine (e.g. `tailscale serve`). The bind itself never leaves
        # loopback: proxied requests still arrive from 127.0.0.1.
        self.extra_hosts = frozenset(name.strip().lower() for name in extra_hosts if name.strip())


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="shadow browse", description=__doc__)
    value.add_argument("--host", default=os.environ.get("SHADOW_BROWSER_HOST") or "127.0.0.1")
    value.add_argument("--port", type=int, default=os.environ.get("SHADOW_BROWSER_PORT") or "7191")
    value.add_argument(
        "--root",
        default=str(_board_import.portfolio_root(Path.cwd())),
    )
    value.add_argument("--no-open", action="store_true")
    value.add_argument(
        "--allow-host",
        action="append",
        default=None,
        metavar="NAME",
        help="also accept this Host header from a proxy you run on this "
        "machine (e.g. your tailnet name via `tailscale serve`); the bind "
        "stays loopback-only",
    )
    return value


def main(argv: list[str] | None = None) -> int:
    global DEV_ROOT
    args = parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        print("shadow browse: host must be loopback", file=sys.stderr)
        return 2
    if not 0 <= args.port <= 65535:
        print("shadow browse: port is outside the valid range", file=sys.stderr)
        return 2
    DEV_ROOT = Path(args.root).expanduser().resolve()
    if not DEV_ROOT.is_dir():
        print("shadow browse: scan root is not a directory", file=sys.stderr)
        return 2
    server = Server(
        (args.host, args.port),
        DEV_ROOT,
        frozenset(args.allow_host or ()),
        home=Path.home(),
    )
    actual = server.server_address[1]
    print(f"Shadow -> http://{args.host}:{actual}", file=sys.stderr, flush=True)
    if not args.no_open:
        address = f"http://{args.host}:{actual}"
        threading.Timer(0.2, lambda: webbrowser.open(address)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
