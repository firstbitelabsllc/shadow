#!/usr/bin/env python3
"""shadow amp — project a paste-ready starting block from a repository's PLAN.md.

The goal is a POINTER to the durable plan, never a second copy of it. A goal
may drive work across many milestones and repos; no 4,000-character block can
carry that detail, so the block carries exactly enough to warm-start a seat —
authority pointer, mode, the selected starting row with its proof, the latest
plan-owned lesson and decision, the milestone's tooling line, and the standing
rails — and defers everything else to the plan.

Deterministic: no LLM, no network. Same plan, same block. The per-milestone
tooling knowledge rides IN the plan (an optional `- tools:` line directly
under the `###` heading); amp only projects it. Pattern, not store.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_root_board as _board  # noqa: E402
import shadow_plan_grammar as _grammar  # noqa: E402

DEFAULT_MAX_CHARS: Final = 4_000
MAX_GIT_VALUE: Final = 200

ROW_RE = _grammar.ROW_RE
FIELD_RE = _grammar.FIELD_RE
BRIEF_KEY_RE: Final = re.compile(r"^- (?P<key>Project|Mode|Priority|Loop): (?P<value>.+)$")
TOOLS_RE: Final = re.compile(r"^- tools: (?P<value>.+)$")
PLAN_LEAD_RE: Final = re.compile(
    r"^- (?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) "
    r"(?P<kind>LESSON|DECISION) (?P<value>.+)$"
)
HASH_RE = _grammar.HASH_RE
ROW_SHAPE_RE: Final = re.compile(r"^- \[")
CONTROL_RE: Final = re.compile(r"[\x00-\x1f\x7f]")
CAPABILITY_RE: Final = re.compile(r"(?<![0-9A-Za-z_-])/([a-z][a-z0-9-]{0,31})\b")
SUPERPOWERS_COMPATIBLE_LEAVES: Final = (
    "verification-before-completion",
    "test-driven-development",
    "systematic-debugging",
    "receiving-code-review",
)
SUPERPOWERS_KNOWN_LEAVES: Final = (
    *SUPERPOWERS_COMPATIBLE_LEAVES,
    "using-git-worktrees",
    "using-superpowers",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "brainstorming",
    "writing-plans",
    "requesting-code-review",
    "writing-skills",
    "subagent-driven-development",
)
SUPERPOWERS_FORBIDDEN_LEAVES: Final = frozenset(
    set(SUPERPOWERS_KNOWN_LEAVES) - set(SUPERPOWERS_COMPATIBLE_LEAVES)
)
SUPERPOWERS_INTENTS: Final = (
    (
        "test-driven-development",
        re.compile(r"\b(?:tdd|test[- ]driven|test first)\b", re.IGNORECASE),
    ),
    (
        "systematic-debugging",
        re.compile(r"\b(?:debug(?:ging)?|root cause|test failure)\b", re.IGNORECASE),
    ),
    (
        "receiving-code-review",
        re.compile(
            r"\b(?:receiv(?:e|ing)(?: code)? review|review feedback)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "verification-before-completion",
        re.compile(
            r"\b(?:verif(?:y|ying|ication)|before completion|proof before done)\b",
            re.IGNORECASE,
        ),
    ),
)
DEFAULT_SKILL_ROOTS: Final = (".claude/skills", ".agents/skills", ".cursor/skills")


def _sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _parse(text: str) -> dict:
    lines = text.splitlines()
    sections = _sections(lines)

    brief: dict[str, str] = {}
    for line in sections.get("Brief", []):
        match = BRIEF_KEY_RE.match(line)
        if match:
            brief.setdefault(match.group("key"), match.group("value").strip())

    milestones: list[dict] = []
    current: dict | None = None
    # Row-shaped lines the grammar rejects are REMEMBERED, never silently
    # dropped: a plan whose open work failed to parse would otherwise read as
    # "every task complete" and send the next seat chaining past real rows.
    unparsed: list[str] = []
    for line in sections.get("Tasks", []):
        if line.startswith("### "):
            current = {"title": line[4:].strip(), "tools": None, "rows": []}
            milestones.append(current)
            continue
        if current is None:
            continue
        tools = TOOLS_RE.match(line)
        if tools and not current["rows"]:
            current["tools"] = tools.group("value").strip()
            continue
        match = ROW_RE.match(line)
        if not match:
            if ROW_SHAPE_RE.match(line):
                unparsed.append(line.strip())
            continue
        row = match.groupdict()
        row["fields"] = {
            m.group("key"): m.group("value").strip()
            for m in FIELD_RE.finditer(row.get("tail") or "")
        }
        current["rows"].append(row)

    contradictions = [
        line for line in sections.get("Contradictions", []) if line.startswith("- ")
    ]
    # Goal minting reuses the plan's append-only knowledge. Only the newest
    # entry of each kind is projected; the plan remains the authority and no
    # parallel dossier, cache, or memory record is created.
    latest_leads: dict[str, tuple[str, str]] = {}
    for line in sections.get("Progress", []):
        match = PLAN_LEAD_RE.match(line)
        if match and (
            match.group("kind") not in latest_leads
            or match.group("ts") > latest_leads[match.group("kind")][0]
        ):
            latest_leads[match.group("kind")] = (
                match.group("ts"),
                match.group("value").strip(),
            )
    leads = [
        f"{kind} {latest_leads[kind][1]}"
        for kind in ("LESSON", "DECISION")
        if kind in latest_leads
    ]
    return {
        "brief": brief,
        "milestones": milestones,
        "contradictions": contradictions,
        "leads": leads,
        "unparsed": unparsed,
        "text": text,
    }


def _completed_ids(milestones: list[dict]) -> set[str]:
    return {
        row["id"]
        for milestone in milestones
        for row in milestone["rows"]
        if row["state"] == "completed"
    }


def _ready(row: dict, done: set[str]) -> bool:
    needs = row["fields"].get("needs", "")
    return all(ref in done for ref in HASH_RE.findall(needs))


def _gated(row: dict) -> bool:
    """A `gate <owner> resume: ...` proof is a person-gated agent-side stop:
    the plan closes there and hands off, so auto-resume must never hand one
    to a seat as its own work. `--task ~hash` stays explicit and may target
    one — that is a person choosing, not the tool choosing for them."""
    return row["fields"].get("proof", "").startswith("gate ")


def _select(plan: dict, task_id: str | None) -> tuple[dict, dict] | None:
    """Return (milestone, row): the in_progress row first, else the first
    ready pending row, milestone order — the same order a cycle resumes in.
    Person-gated rows are never auto-selected."""
    done = _completed_ids(plan["milestones"])
    if task_id:
        for milestone in plan["milestones"]:
            for row in milestone["rows"]:
                if row["id"] == task_id:
                    return milestone, row
        return None
    claimed = plan.get("claimed") or set()
    for state_pass in ("in_progress", "pending"):
        for milestone in plan["milestones"]:
            for row in milestone["rows"]:
                if row["id"] in claimed:
                    continue
                if row["state"] == state_pass and not _gated(row) and (
                    state_pass == "in_progress" or _ready(row, done)
                ):
                    return milestone, row
    return None


def _candidate_ids(plan: dict) -> list[str]:
    """Every currently reachable agent row in deterministic selection order."""
    scratch = dict(plan)
    scratch["claimed"] = set(plan.get("claimed") or set())
    result: list[str] = []
    while selected := _select(scratch, None):
        row = selected[1]["id"]
        result.append(row)
        scratch["claimed"].add(row)
    return result


_LINT: object | None = None
_LINT_TRIED = False


def _lint_blocking(text: str) -> int | None:
    """Blocking `shadow lint` findings for this plan text, or None when the
    linter cannot be loaded. Parsing is deliberately tolerant, so a plan can
    parse into FEWER rows than it really has; only a lint-clean plan may be
    called finished."""
    global _LINT, _LINT_TRIED
    if not _LINT_TRIED:
        _LINT_TRIED = True
        path = Path(__file__).resolve().parent / "shadow-lint.py"
        try:
            spec = importlib.util.spec_from_file_location("shadow_lint", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules.setdefault("shadow_lint", module)
            spec.loader.exec_module(module)
            _LINT = module
        except Exception:  # a missing/broken linter must never break a projection
            _LINT = None
    if _LINT is None:
        return None
    try:
        return sum(
            1 for f in _LINT.lint_plan(text) if f.get("severity") == "blocking"
        )
    except Exception:  # same rule: the linter advises, it does not gate the parse
        return None


def unclean_note(plan: dict) -> str | None:
    """One sentence naming why this plan may not be readable as written, or
    None when it parses clean and lints clean."""
    parts = []
    if plan.get("unparsed"):
        parts.append(f"{len(plan['unparsed'])} row-shaped line(s) the grammar rejects")
    try:
        budget = _board.hot_plan_budget(plan.get("text", "").encode("utf-8"))
    except (_board.BoardError, UnicodeError):
        budget = {"exceeded": []}
    if budget["exceeded"]:
        parts.append(
            "hot plan budget exceeded (" + ", ".join(budget["exceeded"]) + ")"
        )
    blocking = _lint_blocking(plan.get("text", ""))
    if blocking:
        parts.append(f"{blocking} blocking lint finding(s)")
    if not parts:
        return None
    return f"the plan does not read clean — {' and '.join(parts)}; run `shadow lint`"


def stall_reason(plan: dict) -> str:
    """Why auto-resume selected nothing — never 'all complete' while open rows
    remain, and never 'all complete' for a plan whose rows may not all have
    parsed. A plan can stall with work left: every open row person-gated,
    blocked, or waiting on unmet `needs:`. Saying 'mint the successor' there
    would tell a seat to chain past work nobody has done."""
    done = _completed_ids(plan["milestones"])
    open_rows = [
        row
        for milestone in plan["milestones"]
        for row in milestone["rows"]
        if row["state"] != "completed"
    ]
    unclean = unclean_note(plan)
    if not open_rows:
        if unclean:
            return f"{unclean} before chaining a successor over unread work"
        return "every task complete; mint the successor (goal chaining)"
    claimed = plan.get("claimed") or set()
    # A claim is why auto-resume passed over otherwise takeable work, so name
    # that state rather than hiding it inside "other".
    counts = {"person-gated": 0, "blocked": 0, "claimed on this computer": 0,
              "waiting on needs": 0, "other": 0}
    for row in open_rows:
        if _gated(row):
            counts["person-gated"] += 1
        elif row["state"] == "blocked":
            counts["blocked"] += 1
        elif row["id"] in claimed:
            counts["claimed on this computer"] += 1
        elif not _ready(row, done):
            counts["waiting on needs"] += 1
        else:
            counts["other"] += 1
    detail = ", ".join(f"{count} {name}" for name, count in counts.items() if count)
    advice = "hand off, unblock, or mint the successor"
    if counts["claimed on this computer"]:
        advice = ("probe the claimed work with `shadow status --in-flight`, "
                  "hand off, unblock, or mint the successor")
    reason = f"nothing agent-takeable — {len(open_rows)} open row(s): {detail}; {advice}"
    return f"{reason} ({unclean})" if unclean else reason


def _clean(value: str, limit: int = MAX_GIT_VALUE) -> str:
    """Git metadata (a remote URL, a branch name) and free-text Brief values
    are repository-controlled data that land in a block a person pastes into
    an agent prompt. A value carrying newlines could otherwise append its own
    instruction lines, so control characters collapse to spaces and the value
    is bounded. Every such value goes through here — a plan is authority over
    what to work on, never authority over the rails around the work."""
    flat = CONTROL_RE.sub(" ", value).strip()
    return f"{flat[:limit]}…" if len(flat) > limit else flat


def _git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return _clean(out.stdout) if out.returncode == 0 else ""
    except OSError:
        return ""


def _pointer(repo: Path, plan_path: Path) -> tuple[str, bool, bool]:
    """(pointer, dirty, local). `dirty` is true when the plan on disk differs
    from the ref the pointer names — amp read the working tree, so the block
    must say so rather than advertise a ref that serves different content.
    A machine-local plan names no ref at all: nothing can fetch it, and no ref
    ever serves it, so it is never dirty and always points at this computer."""
    local = _board.is_local_plan(plan_path)
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    sha = _git(repo, "rev-parse", "--short", "HEAD")
    rel = plan_path.name if plan_path.parent == repo else str(plan_path.relative_to(repo))
    dirty = (
        not local
        and bool(sha)
        and bool(_git(repo, "status", "--porcelain", "--", str(plan_path)))
    )
    at = " @ this computer" if local else (f" @ {branch}@{sha}" if sha else "")
    if dirty:
        at += " +UNCOMMITTED"
    public = _board.public_plan_locator(plan_path)
    suffix = f"/{rel}"
    where = public[: -len(suffix)] if public.endswith(suffix) else public
    return f"{rel}{at} in {where}", dirty, local


_SLOTS: object | None = None
_SLOTS_TRIED = False
_SLOTS_ERROR: str | None = None


def _slot_api() -> object | None:
    """Load the read-only slot resolver without making amp a package manager."""
    global _SLOTS, _SLOTS_ERROR, _SLOTS_TRIED
    if _SLOTS_TRIED:
        return _SLOTS
    _SLOTS_TRIED = True
    try:
        spec = importlib.util.spec_from_file_location(
            "shadow_slots_for_amp", ROOT / "scripts" / "shadow-slots.py"
        )
        if spec is None or spec.loader is None:
            _SLOTS_ERROR = "module loader unavailable"
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SLOTS = module
        _SLOTS_ERROR = None
    except Exception as error:  # optional resolver defects never gate amp
        _SLOTS = None
        _SLOTS_ERROR = type(error).__name__
    return _SLOTS


def _capability_requests(tools: str, declared: list[dict[str, str]]) -> list[str]:
    """Explicit slash skills and named slots, in declaration-text order."""
    found: list[tuple[int, str]] = [
        (match.start(), match.group(1)) for match in CAPABILITY_RE.finditer(tools)
    ]
    for slot in declared:
        name = slot["name"]
        if name == "memory":
            # Ratified 2026-08-15: 'memory' is a common English word
            # ("profile memory usage" would false-trigger), so the memory
            # slot answers to its slash form only.
            continue
        for match in re.finditer(rf"(?<![0-9A-Za-z_-]){re.escape(name)}\b", tools):
            found.append((match.start(), name))
    result: list[str] = []
    for _, name in sorted(found, key=lambda item: (item[0], item[1])):
        if name not in result:
            result.append(name)
    return result


def _project_tools(tools: str, catalog: frozenset[str] = frozenset()) -> str:
    """Keep project prose and ordinary tools, remove unsafe pack invocations."""
    leaves = set(SUPERPOWERS_KNOWN_LEAVES) | set(catalog)
    root_pattern = re.compile(r"(?<![0-9A-Za-z_-])/?superpowers\b")
    leaf_pattern = re.compile(
        r"(?<![0-9A-Za-z_-])/(?P<name>"
        + "|".join(re.escape(name) for name in sorted(leaves, key=len, reverse=True))
        + r")\b"
    )

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name in SUPERPOWERS_COMPATIBLE_LEAVES:
            return f"Shadow Method intent ({name})"
        return f"Shadow Method fallback ({name} refused)"

    without_root = root_pattern.sub("Shadow Method", tools)
    return leaf_pattern.sub(replace, without_root)


def _read_superpowers_snapshot(
    home: Path,
) -> tuple[dict[str, str], frozenset[str]]:
    """Compatible leaves plus the full installed Superpowers leaf catalog.

    A pack manifest proves only that the pack exists. Selection requires the
    concrete leaf's own SKILL.md; otherwise amp would be inventing a partial
    discipline that no installed capability actually provides. The catalog
    makes the allowlist default-deny: a newly installed pack leaf is refused
    unless Shadow's compatibility set explicitly adopts it.
    """
    roots: list[tuple[Path, str]] = []
    _, override = _pack_root_override()
    if override and override.lower() != "off":
        bound = Path(override)
        roots.append((bound, "explicit binding"))

    cache = home / ".claude" / "plugins" / "cache"
    if cache.is_dir():
        for manifest in sorted(
            cache.glob("*/superpowers/*/.claude-plugin/plugin.json")
        ):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict) or data.get("name") != "superpowers":
                continue
            roots.append((manifest.parent.parent, f"pack {data.get('version', '?')}"))

    catalog: set[str] = set()
    sources: dict[str, str] = {}
    for root, source in roots:
        direct = root / "SKILL.md"
        if direct.is_file():
            catalog.add(root.name)
            sources.setdefault(root.name, source)
        skills = root / "skills"
        if not skills.is_dir():
            continue
        try:
            candidates = sorted(skills.iterdir())
        except OSError:
            continue
        for candidate in candidates:
            if (candidate / "SKILL.md").is_file():
                catalog.add(candidate.name)
                sources.setdefault(candidate.name, source)

    found: dict[str, str] = {}
    for leaf in SUPERPOWERS_COMPATIBLE_LEAVES:
        if leaf in catalog:
            found[leaf] = f"whole Superpowers leaf {leaf} ({sources[leaf]})"
    return found, frozenset(catalog)



def _pack_root_override() -> tuple[str, str]:
    """(variable, value) for the strongest set pack-root override.

    Amp-core configuration — the superpowers slot is gone (2026-08-15) while
    the delegation guard stays core. Legacy names honored one release train.
    Whitespace-only values fall through instead of masking a set legacy name.
    """
    for variable in (
        "SHADOW_AMP_PACK_ROOT",
        "SHADOW_SLOT_SUPERPOWERS",
        "SHADOW_BUCKET_SUPERPOWERS",
    ):
        value = os.environ.get(variable, "").strip()
        if value:
            return variable, value
    return "SHADOW_AMP_PACK_ROOT", ""

def _superpowers_snapshot(
    home: Path,
) -> tuple[dict[str, str], frozenset[str], str | None]:
    """A broken optional cache becomes one deterministic advisory snapshot."""
    try:
        leaves, catalog = _read_superpowers_snapshot(home)
        return leaves, catalog, None
    except Exception as error:
        return {}, frozenset(), type(error).__name__


def _applicable_superpowers_leaf(
    tools: str, leaves: dict[str, str]
) -> str | None:
    """The earliest concrete intent named by the milestone tools line."""
    candidates: list[tuple[int, int, str]] = []
    for rank, (leaf, pattern) in enumerate(SUPERPOWERS_INTENTS):
        if leaf not in leaves:
            continue
        match = pattern.search(tools)
        if match is not None:
            candidates.append((match.start(), rank, leaf))
    return min(candidates)[2] if candidates else None


def _resolve_capability(
    name: str,
    home: Path,
    declared: list[dict[str, str]],
    api: object | None,
    superpowers: tuple[dict[str, str], frozenset[str], str | None] | None = None,
) -> tuple[str, str]:
    leaves, catalog, _snapshot_error = superpowers or _superpowers_snapshot(home)
    pack_variable, pack_value = _pack_root_override()
    superpowers_off = pack_value.lower() == "off"
    if superpowers_off and (
        name == "superpowers"
        or name in SUPERPOWERS_KNOWN_LEAVES
        or name in catalog
    ):
        return (
            "off",
            f"off by {pack_variable} — the emptiness is deliberate",
        )
    if name in SUPERPOWERS_FORBIDDEN_LEAVES or (
        name in catalog and name not in SUPERPOWERS_COMPATIBLE_LEAVES
    ):
        return (
            "warning",
            "incompatible with Shadow-owned planning, claims, delegation, or review flow",
        )

    leaf = leaves.get(name)
    if leaf is not None:
        return "present", leaf
    if name == "superpowers" and leaves:
        return "present", "compatible whole Superpowers leaf installed"

    slot = next(
        (item for item in declared if name in {item["name"], item["default"]}),
        None,
    )
    if slot is not None and api is not None:
        try:
            resolved = api.resolve(slot, home)
        except Exception as error:  # an optional extension can never abort amp
            return (
                "warning",
                f"optional slot resolver unavailable ({type(error).__name__})",
            )
        if (
            not isinstance(resolved, tuple)
            or len(resolved) != 2
            or resolved[0] not in {"pass", "warn", "fail"}
            or not isinstance(resolved[1], str)
        ):
            return "warning", "optional slot resolver returned a malformed result"
        state, detail = resolved
        if "off by " in detail:
            return "off", detail
        return {"pass": "present", "warn": "absent", "fail": "stale"}.get(
            state, "absent"
        ), detail

    try:
        roots = getattr(api, "SKILL_ROOTS", DEFAULT_SKILL_ROOTS)
    except Exception:
        roots = DEFAULT_SKILL_ROOTS
    for root in roots:
        if (home / root / name / "SKILL.md").is_file():
            return "present", f"skill mounted in {root}"
    if name in SUPERPOWERS_KNOWN_LEAVES or name in catalog:
        return "absent", "no installed whole compatible leaf"
    command = shutil.which(name, path=os.environ.get("PATH"))
    if command:
        return "present", f"command on PATH ({Path(command).name})"
    return "absent", "no mounted skill, declared slot, or command on PATH"


def capability_block(
    tools: str,
    home: Path | None = None,
    superpowers: tuple[dict[str, str], frozenset[str], str | None] | None = None,
) -> str | None:
    """Resolve milestone-declared capabilities. Pure read; absence never gates."""
    api = _slot_api()
    declaration_warning: str | None = None
    if api is None:
        declared = []
        suffix = f" ({_SLOTS_ERROR})" if _SLOTS_ERROR else ""
        declaration_warning = f"optional slot declaration resolver unavailable{suffix}"
    else:
        try:
            raw_declarations = list(api.declared())
        except Exception as error:  # declaration failure is advisory, not a packet gate
            declared = []
            declaration_warning = (
                f"optional slot declaration resolver unavailable "
                f"({type(error).__name__})"
            )
        else:
            declared = []
            malformed = False
            try:
                for item in raw_declarations:
                    if not isinstance(item, dict) or not all(
                        isinstance(item.get(field), str) and item[field]
                        for field in ("name", "default")
                    ):
                        malformed = True
                        continue
                    declared.append(item)
            except Exception as error:
                declared = []
                declaration_warning = (
                    f"optional slot declaration resolver unavailable "
                    f"({type(error).__name__})"
                )
            if malformed and declaration_warning is None:
                declaration_warning = (
                    "optional slot declaration resolver returned malformed data"
                )
    requests = _capability_requests(tools, declared)
    if not requests and declaration_warning is None:
        return None
    active_home = home or Path.home()
    superpowers = superpowers or _superpowers_snapshot(active_home)
    superpowers_leaves = superpowers[0]
    projected_tools = _project_tools(tools, superpowers[1])
    reason = _clean(f"declared by milestone tools: {projected_tools}", 180)
    lines = ["CAPABILITIES:"]
    if declaration_warning is not None:
        lines.append(
            "- extension-slots | result: warning | selected: native host + "
            f"Shadow Method | detail: {declaration_warning} | reason: {reason} | "
            "fallback: native host + Shadow Method"
        )
    for name in requests:
        state, detail = _resolve_capability(
            name, active_home, declared, api, superpowers
        )
        selected = f"/{name}" if state == "present" else "native host + Shadow Method"
        scope = ""
        if name == "superpowers":
            compatible = (
                _applicable_superpowers_leaf(tools, superpowers_leaves)
                if superpowers[2] is None
                else None
            )
            if superpowers[2] is not None:
                state = "warning"
                selected = "native host + Shadow Method"
                detail = (
                    "optional Superpowers leaf inspection unavailable "
                    f"({superpowers[2]})"
                )
            elif state == "present" and compatible is not None:
                selected = f"Shadow Method adapted discipline ({compatible})"
                detail = f"{detail}; {superpowers_leaves[compatible]}"
            else:
                selected = "native host + Shadow Method"
                if state == "present":
                    state = "warning"
                    why = (
                        "no compatible whole leaf installed"
                        if not superpowers_leaves
                        else "no applicable compatible leaf named by milestone tools"
                    )
                    detail = f"{detail}; {why}"
            scope = (
                " | adapted discipline: brainstorm and request-review ideas stay in "
                "Shadow Method; Shadow keeps planning and delegation"
            )
        elif name == "memory":
            # The lead-not-authority law rides the packet itself, mirroring
            # the superpowers scope suffix (SPEC §3, 2026-08-15).
            scope = (
                " | scope: lead only — recalled content re-verified at its "
                "attributed source"
            )
        elif name in SUPERPOWERS_COMPATIBLE_LEAVES and state == "present" and (
            name in superpowers_leaves
        ):
            selected = f"Shadow Method adapted discipline ({name})"
        lines.append(
            f"- {name} | result: {state} | selected: {selected} | "
            f"detail: {_clean(str(detail), 120)} | reason: {reason} | "
            f"fallback: native host + Shadow Method{scope}"
        )
    return "\n".join(lines)


def build_block(plan: dict, repo: Path, plan_path: Path,
                task_id: str | None, max_chars: int) -> tuple[str, list[str]]:
    selected = _select(plan, task_id)
    if selected is None:
        raise LookupError(
            stall_reason(plan)
            if task_id is None
            else f"task {task_id} not found in the plan"
        )
    milestone, row = selected
    brief = plan["brief"]
    # Project rides the required header, which never drops, so it needs the
    # same bound as Mode, Priority, and Loop: unbounded, a 3,400-char Project
    # value evicted RAILS from a 4k block while amp still reported success.
    # The default loop derives from the cleaned value so both stay bounded.
    project = _clean(brief.get("Project", repo.name), 64)
    loop = _clean(brief.get("Loop", f"/{project}-loop"), 64)

    dod = next((r for r in milestone["rows"] if r["dod"]), None)
    gates = [
        r for r in milestone["rows"]
        if r["state"] != "completed"
        and r["fields"].get("proof", "").startswith("gate ")
        and r is not row
        and r is not dod  # the DoD gets its own line; never list it twice
    ]

    outcome = re.sub(r"^[A-Z]+\d+\s*[—-]\s*", "", milestone["title"])
    header = f"/goal {project} — {outcome}"
    pointer = plan.get("authority_pointer")
    local_authority = bool(plan.get("local_authority"))
    if pointer is None:
        pointer, dirty, local_authority = _pointer(repo, plan_path)
    else:
        pointer, dirty = _clean(str(pointer), 512), False
    revision = plan.get("board_revision")
    board_line = (
        f"This computer's Shadow board revision {revision} owns project priority, entity "
        "pointers, claims, owners, and resume."
        if revision is not None
        else "This entity is not registered on this computer yet; claim it before handoff."
    )
    if plan.get("entity_id"):
        board_line += f" Entity: {plan['entity_id']}."
    if plan.get("seat_owner"):
        board_line += f" Seat: {plan['seat_owner']}."
    authority = (
        f"AUTHORITY: {pointer} — section \"### {milestone['title']}\".\n"
        f"{board_line}\n"
        "The entity plan owns milestone/checkpoint detail and proof; this block copies "
        "neither. First move:\n"
        + (
            "read that local file directly and state its observed timestamp."
            if local_authority
            else "fetch, read that section at the current origin ref, and state the ref you read."
        )
    )
    if dirty:
        # The block was projected from the WORKING TREE; the named ref serves
        # different content, so the pointer would lie to a seat that fetched
        # it. Say it in the part of the block that never drops.
        authority += (
            "\nUNCOMMITTED: this block was read from the working tree, which differs from\n"
            "the ref above — commit and push the plan before handing this goal to a seat."
        )
    mode_bits = [f"MODE: {_clean(brief.get('Mode', 'explore'), 16)}"]
    priority = plan.get("root_priority", brief.get("Priority"))
    if priority is not None:
        mode_bits.append(f"Priority: {_clean(str(priority))}")
    mode_bits.append(f"Loop: {_clean(loop, 64)}")
    mode_line = " | ".join(mode_bits)

    resume = f"RESUME: [{row['state']}] {row['text']} {row['id']}"
    proof = f"PROOF: {row['fields'].get('proof', 'MISSING — fix the plan before working')}"
    if row["fields"].get("needs"):
        proof += f" | needs: {row['fields']['needs']}"

    # Assembly order is also drop priority: optional parts vanish from the
    # bottom up until the block fits. The pointer and the resume never drop.
    required = [header, "", authority, "", mode_line, resume, proof]
    optional: list[tuple[str, str]] = []
    if plan.get("leads"):
        projected = " | ".join(_clean(lead, 240) for lead in plan["leads"])
        optional.append(("LEADS", f"PLAN LEADS: {projected}"))
    if milestone["tools"]:
        active_home = Path.home()
        superpowers = _superpowers_snapshot(active_home)
        catalog = superpowers[1]
        projected_tools = _project_tools(milestone["tools"], catalog)
        optional.append(("TOOLS", f"TOOLS: {projected_tools}"))
        capabilities = capability_block(
            milestone["tools"], active_home, superpowers
        )
        if capabilities:
            optional.append(("CAPABILITIES", capabilities))
    if dod and dod is not row:
        dod_line = f"DoD: [{dod['state']}] {dod['text']} | proof: {dod['fields'].get('proof', '?')}"
        optional.append(("DOD", dod_line))
    if gates:
        gate_lines = "; ".join(f"{r['text']} {r['id']}" for r in gates)
        optional.append(("GATES", f"PERSON-GATED (do not take): {gate_lines}"))
    if plan["contradictions"]:
        optional.append((
            "CONTRA",
            f"CONTRADICTIONS OPEN: {len(plan['contradictions'])} — read ## Contradictions "
            "before landing any checkpoint.",
        ))
    optional.append((
        "RAILS",
        "RAILS: drain every reachable checkpoint required by the Outcome; fan out safe "
        "path-disjoint claims; park only exact hard-rail wakes; no proof, no completed; "
        "run `shadow lint` before mode flips; append your own Progress receipts, never "
        "rewrite another seat's; keep choosing successors until full acceptance.",
    ))

    kept = list(optional)
    dropped: list[str] = []
    while True:
        block = "\n".join(required + [line for _, line in kept]) + "\n"
        if len(block) <= max_chars or not kept:
            break
        name, _ = kept.pop()
        dropped.append(name)
    if len(block) > max_chars:
        # Name the part that is actually big AND shrinkable. This used to
        # always blame the resume row, sending people to shrink a 30-char task
        # line while an oversized Priority value was the real cause. The
        # authority pointer is deliberately excluded: it is fixed boilerplate
        # that no plan edit can shorten, so naming it is advice nobody can
        # follow — its cost is reported separately as the floor.
        part, size = max(
            (("resume row", len(resume)), ("proof line", len(proof)),
             ("mode/priority line", len(mode_line))),
            key=lambda pair: pair[1],
        )
        raise ValueError(
            f"minimal block is {len(block)} chars (> {max_chars}); {len(header) + len(authority)} "
            f"of that is the fixed authority pointer, and the largest plan-owned part is the "
            f"{part} at {size} chars — raise --max-chars or shrink that line (see READ-FIT)."
        )
    return block, dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shadow amp",
        description="Resume a paste-ready packet already claimed by one stable seat.",
        epilog="Deterministic: no LLM, no network. amp reads a plan file and cannot see "
               "your conversation, so it projects the pointer, not the judgment; the "
               "judgment half is SKILL.md section 'Shape a goal'.",
    )
    parser.add_argument("--repo", default=None, help="repository root (default: cwd)")
    parser.add_argument("--entity", default=None, help="computer-board entity id")
    parser.add_argument("--by", required=True, help="stable seat name for owned-claim resume")
    parser.add_argument("--plan", default=None, help="plan path (default: <repo>/PLAN.md)")
    parser.add_argument("--task", default=None, help="target one row by ~hash instead of auto-resume")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                        help=f"paste budget (default: {DEFAULT_MAX_CHARS})")
    args = parser.parse_args(argv)

    if args.entity and args.repo:
        print("shadow amp: use either --entity or --repo, not both", file=sys.stderr)
        return 2
    if args.entity and args.plan:
        print("shadow amp: --plan cannot override a board entity", file=sys.stderr)
        return 2
    try:
        _board.validate_owner(args.by)
    except _board.BoardError as exc:
        print(f"shadow amp: --by is unsafe: {exc}", file=sys.stderr)
        return 2

    state = None
    if args.entity:
        try:
            resolved = _board.resolve_entity(args.entity)
        except _board.BoardError as exc:
            print(f"shadow amp: {exc}", file=sys.stderr)
            return 1
        if resolved is None or resolved["plan"] is None:
            print("shadow amp: entity is not registered on this computer", file=sys.stderr)
            return 1
        state = resolved["state"]
        plan_path = resolved["plan"]
        repo = plan_path.parent
    else:
        repo = Path(args.repo or ".").resolve()
        if args.plan:
            # A relative --plan is relative to the REPO, not the process cwd.
            given = Path(args.plan)
            unresolved = given if given.is_absolute() else repo / given
            if not _board.regular_plan(unresolved):
                print("shadow amp: plan must be a regular, non-symlink PLAN.md", file=sys.stderr)
                return 2
            plan_path = unresolved.resolve()
        else:
            plan_path = repo / "PLAN.md"
            if not _board.regular_plan(plan_path):
                # A project whose authority is machine-local carries no plan in
                # its checkout; the board already knows where that authority
                # lives, so the repository-shaped verb still resolves it.
                plan_path = _board.local_plan_for_repo(repo) or plan_path
    if args.task and not re.fullmatch(r"~[0-9a-z]{4}", args.task):
        print(f"shadow amp: --task wants a four-char id like ~ab12, got {args.task}",
              file=sys.stderr)
        return 2

    if not args.entity:
        try:
            state = _board.entity_state(plan_path)
            if state is not None and state["entity"] is None:
                print(
                    "shadow amp: this entity is not registered on this computer; "
                    "run shadow status from its portfolio, then retry",
                    file=sys.stderr,
                )
                return 1
            if state is not None:
                plan_path = _board.canonical_plan(plan_path)
        except _board.BoardError as exc:
            print(f"shadow amp: this computer's root board is unreadable: {exc}", file=sys.stderr)
            return 1
    if not _board.regular_plan(plan_path):
        print(f"shadow amp: no plan at {plan_path}", file=sys.stderr)
        return 2
    top = subprocess.run(
        ["git", "-C", str(plan_path.parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode == 0 and top.stdout.strip():
        repo = Path(top.stdout.strip()).resolve()
    try:
        text = _board.read_plan_text(plan_path)
    except _board.BoardError as exc:
        print(f"shadow amp: plan is unreadable: {exc}", file=sys.stderr)
        return 2
    plan = _parse(text)
    selected_task = args.task
    if state is None:
        print(
            "shadow amp: no computer-board claim exists; use shadow throw to claim "
            "the row before projecting an execution packet",
            file=sys.stderr,
        )
        return 1
    if state["entity"] is not None:
        plan["board_revision"] = state["revision"]
        plan["claimed"] = {claim["row"] for claim in state["claims"]}
        plan["root_priority"] = state["project"]["priority"]
        plan["entity_id"] = state["entity"]["id"]
        plan["seat_owner"] = args.by
        owners = {claim["row"]: claim["owner"] for claim in state["claims"]}
        row_states = {
            row["id"]: row["state"]
            for milestone in plan["milestones"]
            for row in milestone["rows"]
        }
        if selected_task and owners.get(selected_task) != args.by:
            detail = (
                f"claimed by {owners[selected_task]}"
                if selected_task in owners
                else "not claimed"
            )
            print(f"shadow amp: {selected_task} is {detail}; claim it first", file=sys.stderr)
            return 1
        if selected_task and row_states.get(selected_task) not in {"pending", "in_progress"}:
            state_name = row_states.get(selected_task, "missing")
            wake = (
                f"shadow return --entity {state['entity']['id']} "
                f"--row {shlex.quote(selected_task)} --by {shlex.quote(args.by)}"
            )
            print(
                f"shadow amp: {selected_task} is {state_name}, not executable work; run {wake}",
                file=sys.stderr,
            )
            return 1
        owned = [row for row, owner in owners.items() if owner == args.by]
        if selected_task is None and not owned:
            resume = state["entity"]["resume"]
            wake = (
                f"run shadow throw --entity {state['entity']['id']} "
                f"--task {shlex.quote(resume)} --by {shlex.quote(args.by)}"
                if resume
                else "choose and claim a reachable row first"
            )
            print(
                f"shadow amp: no row on this entity is claimed by {args.by}; {wake}",
                file=sys.stderr,
            )
            return 1
        if selected_task is None:
            ordered = [
                row["id"]
                for milestone in plan["milestones"]
                for row in milestone["rows"]
            ]
            resume = state["entity"]["resume"]
            active_owned = [
                row for row in ordered
                if row in owned and row_states.get(row) in {"pending", "in_progress"}
            ]
            if not active_owned:
                recovery = next((row for row in ordered if row in owned), sorted(owned)[0])
                state_name = row_states.get(recovery, "missing")
                wake = (
                    f"shadow return --entity {state['entity']['id']} "
                    f"--row {shlex.quote(recovery)} --by {shlex.quote(args.by)}"
                )
                print(
                    f"shadow amp: owned row {recovery} is {state_name}, not executable work; "
                    f"run {wake}",
                    file=sys.stderr,
                )
                return 1
            selected_task = resume if resume in active_owned else active_owned[0]
    try:
        block, dropped = build_block(plan, repo, plan_path, selected_task, args.max_chars)
    except LookupError as err:
        print(f"shadow amp: no goal to project — {err}.", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"shadow amp: {err}", file=sys.stderr)
        return 1

    sys.stdout.write(block)
    unclean = unclean_note(plan)
    if unclean:
        print(f"shadow amp: warning — {unclean}; rows it rejected are not in this block",
              file=sys.stderr)
    note = f"[amp] {len(block)}/{args.max_chars} chars"
    if dropped:
        note += f"; dropped to fit: {', '.join(dropped)} (all still in the plan)"
    print(note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
