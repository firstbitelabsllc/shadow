#!/usr/bin/env python3
"""Model-authored chief-of-staff projection over a bounded Shadow packet.

This module never collects provider data, schedules work, sends mail, or falls
back to deterministic prose. It projects already-collected evidence, invokes
one explicitly configured native Codex or Claude Code host, validates exact
source references, and writes a private artifact only after success.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "config" / "chief-of-staff-author.json"
RESULT_SCHEMA_PATH = ROOT / "schemas" / "chief-of-staff-letter.v1.json"
PROMPT_PATH = ROOT / "docs" / "reference" / "chief-of-staff-authoring.md"
EVIDENCE_SCHEMA = "shadow.chief-of-staff-evidence.v1"
LETTER_SCHEMA = "shadow.chief-of-staff-letter.v1"
ARTIFACT_SCHEMA = "shadow.chief-of-staff-authored-artifact.v1"
RECEIPT_SCHEMA = "shadow.chief-of-staff-author-receipt.v1"
SECTION_NAMES = (
    "what_matters",
    "decisions_made",
    "needs_leo",
    "people_waiting",
    "risks",
    "next_owned_moves",
    "coverage_gaps",
)


class AuthoringError(ValueError):
    """The authoring contract could not produce a trustworthy letter."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def load_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AuthoringError(f"author profile unavailable: {exc}") from exc
    if not isinstance(profile, dict):
        raise AuthoringError("author profile must be a JSON object")
    if profile.get("schema") != "shadow.chief-of-staff-author-profile.v1":
        raise AuthoringError("author profile schema is unsupported")
    hosts = profile.get("allowed_hosts")
    if hosts != ["codex", "claude-code"]:
        raise AuthoringError("author profile must allow exactly codex and claude-code")
    if profile.get("default_host") is not None:
        raise AuthoringError("author profile must fail closed without an explicit host")
    expected = profile.get("expected_identities")
    if not isinstance(expected, list) or not expected or any(
        not isinstance(value, str) or not value for value in expected
    ):
        raise AuthoringError("author profile expected identities are invalid")
    for key in ("evidence_caps", "section_caps"):
        caps = profile.get(key)
        if not isinstance(caps, dict) or any(
            not isinstance(value, int) or value < 0 for value in caps.values()
        ):
            raise AuthoringError(f"author profile {key} are invalid")
    reader_max = profile.get("reader_max_characters")
    patterns = profile.get("reader_forbidden_patterns")
    if not isinstance(reader_max, int) or reader_max < 500 or reader_max > 10000:
        raise AuthoringError("author profile reader character cap is invalid")
    if not isinstance(patterns, list) or any(
        not isinstance(pattern, str) or not pattern for pattern in patterns
    ):
        raise AuthoringError("author profile reader forbidden patterns are invalid")
    pinned_terms = profile.get("pinned_progress_terms")
    if not isinstance(pinned_terms, list) or any(
        not isinstance(term, str) or not term for term in pinned_terms
    ):
        raise AuthoringError("author profile pinned progress terms are invalid")
    required_rules = profile.get("reader_required_if_evidence")
    if not isinstance(required_rules, list) or any(
        not isinstance(rule, dict)
        or set(rule) != {"evidence_term", "reader_pattern", "description"}
        or any(not isinstance(rule.get(key), str) or not rule[key] for key in rule)
        for rule in required_rules
    ):
        raise AuthoringError("author profile conditional reader requirements are invalid")
    try:
        for pattern in patterns:
            re.compile(pattern, re.IGNORECASE)
        for rule in required_rules:
            re.compile(rule["reader_pattern"], re.IGNORECASE)
    except re.error as exc:
        raise AuthoringError(f"author profile reader pattern is invalid: {exc}") from exc
    timeout = profile.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout < 30 or timeout > 900:
        raise AuthoringError("author profile timeout is invalid")
    return profile


def _bounded_dict(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: value.get(key) for key in keys if key in value}


def _sanitize_fact(value: Any, *, depth: int = 0) -> Any:
    """Keep one hostile provider/plan value from making the prompt unbounded."""
    if depth >= 5:
        return "[nested value omitted]"
    if isinstance(value, str):
        return value if len(value) <= 1200 else value[:1199] + "…"
    if isinstance(value, list):
        return [_sanitize_fact(item, depth=depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        return {
            str(key)[:120]: _sanitize_fact(item, depth=depth + 1)
            for key, item in list(value.items())[:30]
        }
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _sanitize_fact(str(value), depth=depth + 1)


def build_evidence_projection(
    packet: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Build a bounded fact appendix without deciding what matters."""
    if not isinstance(packet, dict):
        raise AuthoringError("source packet must be a JSON object")
    caps = profile["evidence_caps"]
    facts: list[dict[str, Any]] = []
    known_refs: set[str] = set()

    def add(ref: str, kind: str, fact: Any) -> None:
        if ref in known_refs:
            return
        known_refs.add(ref)
        facts.append({"ref": ref, "kind": kind, "fact": _sanitize_fact(fact)})

    board = packet.get("board") if isinstance(packet.get("board"), dict) else {}
    add(
        "packet.board",
        "authority",
        _bounded_dict(board, ("revision", "schema", "projects")),
    )
    claims = board.get("claims") if isinstance(board.get("claims"), list) else []
    for index, claim in enumerate(claims[: caps["claims"]]):
        add(
            f"packet.board.claims.{index}",
            "active_claim",
            _bounded_dict(
                claim,
                ("project", "row", "owner", "claimed_at", "return_by"),
            ),
        )
    entities = board.get("entities") if isinstance(board.get("entities"), list) else []
    for entity_index, entity in enumerate(entities[: caps["entities"]]):
        if not isinstance(entity, dict):
            continue
        entity_ref = f"packet.board.entities.{entity_index}"
        add(
            f"{entity_ref}.status",
            "entity_status",
            _bounded_dict(
                entity,
                ("project", "mode", "priority", "resume", "availability", "wake"),
            ),
        )
        checkpoints = entity.get("open_checkpoints")
        if isinstance(checkpoints, list):
            for item_index, item in enumerate(
                checkpoints[: caps["open_checkpoint_per_entity"]]
            ):
                add(
                    f"{entity_ref}.open_checkpoints.{item_index}",
                    "open_checkpoint",
                    _bounded_dict(item, ("id", "title", "state", "milestone")),
                )
        progress = entity.get("recent_progress")
        if isinstance(progress, list):
            selected = list(progress[-caps["entity_progress_per_entity"] :])
            for item in progress:
                if any(term in str(item) for term in profile["pinned_progress_terms"]):
                    selected.append(item)
            selected = list(dict.fromkeys(str(item) for item in selected))
            for item_index, item in enumerate(selected):
                add(
                    f"{entity_ref}.recent_progress.{item_index}",
                    "recent_progress",
                    str(item),
                )

    mail = (
        packet.get("superhuman_context")
        if isinstance(packet.get("superhuman_context"), dict)
        else {}
    )
    add(
        "packet.superhuman.summary",
        "mail_coverage",
        _bounded_dict(
            mail,
            (
                "status",
                "available",
                "complete",
                "all_clear_allowed",
                "observed_at",
                "query_range",
                "expected_identities",
                "problems",
                "wake",
                "threads_unique",
            ),
        ),
    )
    coverage = mail.get("coverage") if isinstance(mail.get("coverage"), list) else []
    covered_identities: set[str] = set()
    for index, row in enumerate(coverage[: caps["identity_coverage"]]):
        if isinstance(row, dict):
            for key in ("expected_email", "acting_email"):
                identity = row.get(key)
                if isinstance(identity, str) and identity:
                    covered_identities.add(identity)
        add(
            f"packet.superhuman.coverage.{index}",
            "mail_identity_coverage",
            _bounded_dict(
                row,
                (
                    "expected_email",
                    "acting_email",
                    "linked",
                    "status",
                    "observed_at",
                    "problem",
                    "wake",
                ),
            ),
        )
    for index, identity in enumerate(profile["expected_identities"]):
        if identity in covered_identities:
            continue
        add(
            f"packet.superhuman.coverage.missing.{index}",
            "mail_identity_coverage",
            {
                "expected_email": identity,
                "linked": False,
                "status": "UNKNOWN",
                "wake": (
                    f"The source packet has no independent coverage row for {identity}; "
                    "link or re-read that exact Superhuman identity before any all-clear."
                ),
            },
        )
    for category in ("urgent_replies", "forgotten_obligations", "waiting_replies"):
        rows = mail.get(category) if isinstance(mail.get(category), list) else []
        for index, row in enumerate(rows[: caps["mail_candidates_per_kind"]]):
            add(
                f"packet.superhuman.{category}.{index}",
                "mail_candidate",
                _bounded_dict(
                    row,
                    (
                        "subject",
                        "last_message_at",
                        "thread_id",
                        "source_identities",
                        "semantic_status",
                        "confidence",
                        "source_observed_at",
                        "message_age_hours",
                        "waiting_direction",
                        "wake",
                    ),
                ),
            )

    repos = packet.get("repos") if isinstance(packet.get("repos"), list) else []
    changed_repos = [
        repo
        for repo in repos
        if isinstance(repo, dict)
        and (
            repo.get("dirty")
            or repo.get("ahead")
            or repo.get("behind")
            or (
                isinstance(repo.get("last_commit_age_h"), (int, float))
                and repo["last_commit_age_h"] <= 24
            )
        )
    ]
    changed_repos.sort(
        key=lambda repo: (
            repo.get("last_commit_age_h")
            if isinstance(repo.get("last_commit_age_h"), (int, float))
            else 10**9,
            str(repo.get("name") or ""),
        )
    )
    for index, repo in enumerate(changed_repos[: caps["repositories"]]):
        add(
            f"packet.repositories.{index}",
            "repository_change",
            _bounded_dict(
                repo,
                (
                    "name",
                    "branch",
                    "dirty",
                    "ahead",
                    "behind",
                    "last_commit_age_h",
                    "last_subject",
                ),
            ),
        )

    pulls = (
        packet.get("github_open_prs")
        if isinstance(packet.get("github_open_prs"), list)
        else []
    )
    for index, pull in enumerate(pulls[: caps["pull_requests"]]):
        add(
            f"packet.github_open_prs.{index}",
            "pull_request",
            _bounded_dict(
                pull,
                ("repository", "title", "updatedAt", "url", "isDraft"),
            ),
        )

    snowcubes = (
        packet.get("snowcubes_context")
        if isinstance(packet.get("snowcubes_context"), dict)
        else {}
    )
    surfaces = (
        snowcubes.get("surfaces")
        if isinstance(snowcubes.get("surfaces"), list)
        else []
    )
    for index, surface in enumerate(surfaces[: caps["snowcubes_surfaces"]]):
        add(
            f"packet.snowcubes.surfaces.{index}",
            "snowcubes_surface",
            _bounded_dict(
                surface,
                ("name", "state", "now", "next", "source", "observed_at", "wake"),
            ),
        )

    return {
        "schema": EVIDENCE_SCHEMA,
        "generated_at": packet.get("generated_at"),
        "slot": packet.get("slot"),
        "source_packet_sha256": sha256_json(packet),
        "expected_identities": list(profile["expected_identities"]),
        "facts": facts,
    }


def validate_letter(
    letter: Any,
    evidence: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(letter, dict):
        raise AuthoringError("model result must be a JSON object")
    expected_keys = {"schema", "verdict", *SECTION_NAMES, "closing"}
    if set(letter) != expected_keys or letter.get("schema") != LETTER_SCHEMA:
        raise AuthoringError("model result does not match the chief-of-staff schema")
    known_refs = {
        row.get("ref")
        for row in evidence.get("facts", [])
        if isinstance(row, dict) and isinstance(row.get("ref"), str)
    }
    reader_text: list[str] = []
    cited_refs: set[str] = set()
    for name in ("verdict", "closing"):
        value = letter.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > 280:
            raise AuthoringError(f"model result {name} is invalid")
        reader_text.append(value.strip())
    total_items = 0
    normalized_items: set[str] = set()
    for section in SECTION_NAMES:
        rows = letter.get(section)
        cap = profile["section_caps"][section]
        if not isinstance(rows, list) or len(rows) > cap:
            raise AuthoringError(f"model result {section} exceeds its section cap")
        total_items += len(rows)
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"text", "source_refs"}:
                raise AuthoringError(f"model result {section} has an invalid item")
            text = row.get("text")
            refs = row.get("source_refs")
            if not isinstance(text, str) or not text.strip() or len(text) > 480:
                raise AuthoringError(f"model result {section} has invalid prose")
            normalized = re.sub(r"\s+", " ", text.strip()).casefold()
            if normalized in normalized_items:
                raise AuthoringError("model result repeats the same reader item")
            normalized_items.add(normalized)
            reader_text.append(text.strip())
            if (
                not isinstance(refs, list)
                or not refs
                or len(refs) != len(set(refs))
                or any(ref not in known_refs for ref in refs)
            ):
                raise AuthoringError(f"model result {section} cites unknown evidence")
            cited_refs.update(refs)
    if total_items == 0:
        raise AuthoringError("model result contains no cited judgment")
    reader_body = "\n".join(reader_text)
    if len(reader_body) > profile["reader_max_characters"]:
        raise AuthoringError("model result exceeds the reader character cap")
    for pattern in profile["reader_forbidden_patterns"]:
        if re.search(pattern, reader_body, re.IGNORECASE):
            raise AuthoringError(
                f"model result contains forbidden reader-body pattern: {pattern}"
            )
    for rule in profile["reader_required_if_evidence"]:
        matching_refs = {
            row["ref"]
            for row in evidence.get("facts", [])
            if isinstance(row, dict)
            and isinstance(row.get("ref"), str)
            and rule["evidence_term"] in str(row.get("fact"))
        }
        if not matching_refs:
            continue
        if not matching_refs.intersection(cited_refs):
            raise AuthoringError(
                f"model result omits controlling evidence: {rule['description']}"
            )
        if not re.search(rule["reader_pattern"], reader_body, re.IGNORECASE):
            raise AuthoringError(
                f"model result obscures controlling evidence: {rule['description']}"
            )
    return letter


def validate_artifact(
    artifact: Any,
    profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(artifact, dict) or artifact.get("schema") != ARTIFACT_SCHEMA:
        raise AuthoringError("authored artifact schema is unsupported")
    if set(artifact) != {"schema", "letter", "author_receipt", "evidence"}:
        raise AuthoringError("authored artifact fields are invalid")
    evidence = artifact.get("evidence")
    receipt = artifact.get("author_receipt")
    if not isinstance(evidence, dict) or evidence.get("schema") != EVIDENCE_SCHEMA:
        raise AuthoringError("authored artifact evidence is invalid")
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != RECEIPT_SCHEMA
        or receipt.get("status") != "ok"
        or receipt.get("evidence_sha256") != sha256_json(evidence)
    ):
        raise AuthoringError("authored artifact host receipt does not bind its evidence")
    letter = validate_letter(artifact.get("letter"), evidence, profile)
    if receipt.get("letter_sha256") != sha256_json(letter):
        raise AuthoringError("authored artifact host receipt does not bind its letter")
    return letter, evidence, receipt


SECTION_LABELS = {
    "what_matters": "What matters",
    "decisions_made": "Decisions made",
    "needs_leo": "Needs you",
    "people_waiting": "People waiting",
    "risks": "Risks I’m carrying",
    "next_owned_moves": "What I’ll do next",
    "coverage_gaps": "What I can’t see yet",
}


def render_letter_html(artifact: dict[str, Any], profile: dict[str, Any]) -> str:
    letter, evidence, receipt = validate_artifact(artifact, profile)
    fact_index = {
        row["ref"]: row
        for row in evidence["facts"]
        if isinstance(row, dict) and isinstance(row.get("ref"), str)
    }
    used_refs: list[str] = []
    sections: list[str] = []
    for name in SECTION_NAMES:
        rows = letter[name]
        if not rows:
            continue
        items: list[str] = []
        for row in rows:
            for ref in row["source_refs"]:
                if ref not in used_refs:
                    used_refs.append(ref)
            refs = " ".join(
                f'<span class="ref">{html_lib.escape(ref)}</span>'
                for ref in row["source_refs"]
            )
            items.append(
                '<li><p>'
                + html_lib.escape(row["text"])
                + f'</p><div class="refs" aria-label="Evidence references">{refs}</div></li>'
            )
        sections.append(
            f'<section><h2>{html_lib.escape(SECTION_LABELS[name])}</h2>'
            f'<ul>{"".join(items)}</ul></section>'
        )
    appendix_rows: list[str] = []
    for ref in used_refs:
        source = fact_index[ref]
        fact = json.dumps(source["fact"], ensure_ascii=False, sort_keys=True)
        appendix_rows.append(
            '<li><code>'
            + html_lib.escape(ref)
            + '</code><span>'
            + html_lib.escape(fact)
            + '</span></li>'
        )
    generated = html_lib.escape(str(evidence.get("generated_at") or "time unavailable"))
    host = html_lib.escape(str(receipt.get("host") or "model host unavailable"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chief-of-staff brief</title>
<style>
:root {{ color-scheme: light; --ink:#1d241f; --muted:#667067; --paper:#f6f4ed; --card:#fffefa; --line:#d8d7ce; --green:#254f3b; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font-family:ui-serif,Georgia,Cambria,"Times New Roman",serif; line-height:1.5; }}
main {{ width:min(760px,calc(100% - 32px)); margin:0 auto; padding:56px 0 72px; }}
.eyebrow {{ margin:0 0 14px; color:var(--green); font:700 12px/1.2 ui-sans-serif,system-ui,sans-serif; letter-spacing:.12em; text-transform:uppercase; }}
h1 {{ margin:0; max-width:18ch; font-size:clamp(34px,7vw,62px); font-weight:500; letter-spacing:-.035em; line-height:1.03; }}
.meta {{ margin:20px 0 42px; color:var(--muted); font:14px/1.5 ui-sans-serif,system-ui,sans-serif; }}
section {{ border-top:1px solid var(--line); padding:26px 0 18px; }}
h2 {{ margin:0 0 14px; color:var(--green); font:700 13px/1.2 ui-sans-serif,system-ui,sans-serif; letter-spacing:.08em; text-transform:uppercase; }}
ul {{ list-style:none; margin:0; padding:0; }}
section li {{ padding:12px 0; }}
section li + li {{ border-top:1px solid color-mix(in srgb,var(--line) 70%,transparent); }}
section p {{ margin:0; font-size:clamp(18px,2.7vw,22px); letter-spacing:-.008em; }}
.refs {{ display:none; }}
.closing {{ margin:34px 0 0; padding:26px; border-radius:16px; background:var(--green); color:#fff; font-size:22px; }}
details {{ margin-top:42px; border-top:1px solid var(--line); padding-top:20px; color:var(--muted); font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace; }}
summary {{ cursor:pointer; font-family:ui-sans-serif,system-ui,sans-serif; font-weight:700; color:var(--ink); }}
details ol {{ padding-left:20px; }} details li {{ margin:14px 0; }} details code {{ display:block; color:var(--green); }} details span {{ overflow-wrap:anywhere; }}
@media (max-width:520px) {{ main {{ width:min(100% - 24px,760px); padding:30px 0 48px; }} h1 {{ font-size:38px; }} .meta {{ margin-bottom:28px; }} section {{ padding-top:22px; }} .closing {{ margin-top:24px; padding:20px; font-size:19px; }} }}
</style>
</head>
<body><main>
<p class="eyebrow">Private · {html_lib.escape(str(evidence.get("slot") or "brief"))}</p>
<h1>{html_lib.escape(letter["verdict"])}</h1>
<p class="meta">Observed {generated} · Authored by {host}</p>
{"".join(sections)}
<p class="closing">{html_lib.escape(letter["closing"])}</p>
<details><summary>Private evidence appendix · {len(used_refs)} cited facts</summary><ol>{"".join(appendix_rows)}</ol></details>
</main></body></html>
"""


def resolve_host(
    profile: dict[str, Any],
    explicit_host: str | None,
    environ: dict[str, str],
) -> str:
    host = explicit_host or environ.get(str(profile["author_host_env"]))
    if not host:
        raise AuthoringError(
            f"set {profile['author_host_env']} to codex or claude-code; "
            "the deterministic collector cannot author the letter"
        )
    if host not in profile["allowed_hosts"]:
        raise AuthoringError(f"unsupported author host: {host}")
    return host


def _extract_claude_result(stdout: str) -> Any:
    envelope = json.loads(stdout)
    if isinstance(envelope, dict) and isinstance(envelope.get("structured_output"), dict):
        return envelope["structured_output"]
    if isinstance(envelope, dict) and isinstance(envelope.get("result"), str):
        return json.loads(envelope["result"])
    return envelope


def invoke_author(
    evidence: dict[str, Any],
    profile: dict[str, Any],
    *,
    host: str,
    model: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    environ: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    executable = "codex" if host == "codex" else "claude"
    resolved = shutil.which(executable)
    if resolved is None:
        raise AuthoringError(f"configured author host is unavailable: {executable}")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    prompt += "\n\nReturn only the schema-valid JSON letter for this evidence:\n"
    prompt += json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
    timeout = int(profile["timeout_seconds"])
    result: Any
    command: list[str]
    with tempfile.TemporaryDirectory(prefix="shadow-brief-author-") as temp_name:
        temp = Path(temp_name)
        if host == "codex":
            result_path = temp / "result.json"
            command = [
                resolved,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--output-schema",
                str(RESULT_SCHEMA_PATH),
                "--output-last-message",
                str(result_path),
            ]
            if model:
                command.extend(("--model", model))
            command.append("-")
            completed = runner(
                command,
                input=prompt,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=environ,
            )
            if completed.returncode != 0:
                raise AuthoringError(
                    f"codex author failed with exit {completed.returncode}; no letter emitted"
                )
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, RecursionError) as exc:
                raise AuthoringError(f"codex author returned invalid JSON: {exc}") from exc
        else:
            schema = RESULT_SCHEMA_PATH.read_text(encoding="utf-8")
            command = [
                resolved,
                "--print",
                "--no-session-persistence",
                "--permission-mode",
                "dontAsk",
                "--tools",
                "",
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--output-format",
                "json",
                "--json-schema",
                schema,
            ]
            if model:
                command.extend(("--model", model))
            completed = runner(
                command,
                input=prompt,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=environ,
            )
            if completed.returncode != 0:
                raise AuthoringError(
                    f"claude-code author failed with exit {completed.returncode}; no letter emitted"
                )
            try:
                result = _extract_claude_result(completed.stdout)
            except (ValueError, RecursionError) as exc:
                raise AuthoringError(f"claude-code author returned invalid JSON: {exc}") from exc
    letter = validate_letter(result, evidence, profile)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "ok",
        "host": host,
        "host_executable": resolved,
        "requested_model": model,
        "model_observed": None,
        "profile_sha256": sha256_json(profile),
        "prompt_sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        "evidence_sha256": sha256_json(evidence),
        "letter_sha256": sha256_json(letter),
        "authored_at": datetime.now(timezone.utc).isoformat(),
        "tools_allowed": False if host == "claude-code" else "read-only sandbox",
    }
    return letter, receipt


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def cmd_project(args: argparse.Namespace) -> int:
    profile = load_profile(Path(args.profile))
    packet = json.loads(Path(args.input).read_text(encoding="utf-8"))
    evidence = build_evidence_projection(packet, profile)
    write_private_json(Path(args.output), evidence)
    print(args.output)
    return 0


def cmd_author(args: argparse.Namespace) -> int:
    output = Path(args.output)
    try:
        profile = load_profile(Path(args.profile))
        packet = json.loads(Path(args.input).read_text(encoding="utf-8"))
        evidence = build_evidence_projection(packet, profile)
        host = resolve_host(profile, args.host, dict(os.environ))
        letter, receipt = invoke_author(
            evidence,
            profile,
            host=host,
            model=args.model,
            environ=dict(os.environ),
        )
        artifact = {
            "schema": ARTIFACT_SCHEMA,
            "letter": letter,
            "author_receipt": receipt,
            "evidence": evidence,
        }
        write_private_json(output, artifact)
    except (AuthoringError, OSError, ValueError, RecursionError, subprocess.TimeoutExpired) as exc:
        blocked = {
            "schema": RECEIPT_SCHEMA,
            "status": "blocked",
            "wake": str(exc),
            "output_written": False,
        }
        print(json.dumps(blocked, indent=2), file=sys.stderr)
        return 1
    print(str(output))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    try:
        profile = load_profile(Path(args.profile))
        artifact = json.loads(Path(args.input).read_text(encoding="utf-8"))
        rendered = render_letter_html(artifact, profile)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(output, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
    except (AuthoringError, OSError, ValueError, RecursionError) as exc:
        print(json.dumps({"status": "blocked", "wake": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(str(output))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shadow-brief-author")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("project", cmd_project), ("author", cmd_author)):
        command = sub.add_parser(name)
        command.add_argument("--input", required=True)
        command.add_argument("--output", required=True)
        command.add_argument("--profile", default=str(PROFILE_PATH))
        if name == "author":
            command.add_argument("--host", choices=("codex", "claude-code"))
            command.add_argument("--model")
        command.set_defaults(func=handler)
    render = sub.add_parser("render")
    render.add_argument("--input", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--profile", default=str(PROFILE_PATH))
    render.set_defaults(func=cmd_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
