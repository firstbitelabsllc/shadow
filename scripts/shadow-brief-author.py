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
import json
import os
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
            selected = progress[-caps["entity_progress_per_entity"] :]
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
    for name in ("verdict", "closing"):
        value = letter.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > 280:
            raise AuthoringError(f"model result {name} is invalid")
    total_items = 0
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
            if (
                not isinstance(refs, list)
                or not refs
                or len(refs) != len(set(refs))
                or any(ref not in known_refs for ref in refs)
            ):
                raise AuthoringError(f"model result {section} cites unknown evidence")
    if total_items == 0:
        raise AuthoringError("model result contains no cited judgment")
    return letter


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
