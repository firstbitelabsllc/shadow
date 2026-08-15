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
CUSTOMER_PROFILE_PATH = ROOT / "config" / "snowcubes-customer-opportunity-author.json"
CUSTOMER_RESULT_SCHEMA_PATH = (
    ROOT / "schemas" / "snowcubes-customer-opportunity-letter.v1.json"
)
CUSTOMER_PROMPT_PATH = (
    ROOT / "docs" / "reference" / "snowcubes-customer-opportunity-authoring.md"
)
EVIDENCE_SCHEMA = "shadow.chief-of-staff-evidence.v1"
LETTER_SCHEMA = "shadow.chief-of-staff-letter.v1"
ARTIFACT_SCHEMA = "shadow.chief-of-staff-authored-artifact.v1"
RECEIPT_SCHEMA = "shadow.chief-of-staff-author-receipt.v1"
CUSTOMER_EVIDENCE_SCHEMA = "shadow.snowcubes-customer-opportunity-evidence.v1"
CUSTOMER_LETTER_SCHEMA = "shadow.snowcubes-customer-opportunity-letter.v1"
CUSTOMER_ARTIFACT_SCHEMA = "shadow.snowcubes-customer-opportunity-artifact.v1"
CUSTOMER_RECEIPT_SCHEMA = "shadow.snowcubes-customer-opportunity-author-receipt.v1"
SECTION_NAMES = (
    "what_matters",
    "decisions_made",
    "needs_leo",
    "people_waiting",
    "risks",
    "next_owned_moves",
    "coverage_gaps",
)
MAIL_ACTION_CATEGORIES = (
    "urgent_replies",
    "waiting_replies",
    "forgotten_obligations",
    "order_return_follow_up",
    "proactive_candidates",
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
    if (
        not isinstance(expected, list)
        or not expected
        or any(not isinstance(value, str) or not value for value in expected)
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
        raise AuthoringError(
            "author profile conditional reader requirements are invalid"
        )
    try:
        for pattern in patterns:
            re.compile(pattern, re.IGNORECASE)
        for rule in required_rules:
            re.compile(rule["reader_pattern"], re.IGNORECASE)
    except re.error as exc:
        raise AuthoringError(
            f"author profile reader pattern is invalid: {exc}"
        ) from exc
    timeout = profile.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout < 30 or timeout > 900:
        raise AuthoringError("author profile timeout is invalid")
    return profile


def load_customer_profile(path: Path = CUSTOMER_PROFILE_PATH) -> dict[str, Any]:
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AuthoringError(
            f"customer-opportunity author profile unavailable: {exc}"
        ) from exc
    if not isinstance(profile, dict):
        raise AuthoringError(
            "customer-opportunity author profile must be a JSON object"
        )
    if (
        profile.get("schema")
        != "shadow.snowcubes-customer-opportunity-author-profile.v1"
    ):
        raise AuthoringError(
            "customer-opportunity author profile schema is unsupported"
        )
    if profile.get("allowed_hosts") != ["codex", "claude-code"]:
        raise AuthoringError(
            "customer-opportunity author profile must allow exactly codex and claude-code"
        )
    if profile.get("default_host") is not None:
        raise AuthoringError(
            "customer-opportunity author profile must fail closed without an explicit host"
        )
    for key in ("expected_mail_account", "expected_shopify_store", "author_host_env"):
        if not isinstance(profile.get(key), str) or not profile[key]:
            raise AuthoringError(
                f"customer-opportunity author profile {key} is invalid"
            )
    cap = profile.get("opportunity_cap")
    reader_max = profile.get("reader_max_characters")
    max_source_age = profile.get("max_source_age_hours")
    timeout = profile.get("timeout_seconds")
    if not isinstance(cap, int) or cap < 1 or cap > 20:
        raise AuthoringError("customer-opportunity cap is invalid")
    if not isinstance(reader_max, int) or reader_max < 500 or reader_max > 12000:
        raise AuthoringError("customer-opportunity reader character cap is invalid")
    if (
        not isinstance(max_source_age, (int, float))
        or isinstance(max_source_age, bool)
        or max_source_age <= 0
        or max_source_age > 168
    ):
        raise AuthoringError("customer-opportunity source age cap is invalid")
    if not isinstance(timeout, int) or timeout < 30 or timeout > 900:
        raise AuthoringError("customer-opportunity author timeout is invalid")
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


def _mail_opaque_provider_ids(mail: Any) -> set[str]:
    """Collect private provider identities before projecting reader prose."""
    opaque: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return
        for key, item in value.items():
            if key in {"thread_id", "last_message_id", "signal_id", "provider_key"}:
                if isinstance(item, str) and item.strip():
                    opaque.add(item.strip())
            visit(item)

    visit(mail)
    return opaque


def _redact_mail_provider_ids(value: Any, opaque_ids: set[str]) -> Any:
    if isinstance(value, str):
        redacted = value
        for opaque_id in sorted(opaque_ids, key=len, reverse=True):
            redacted = redacted.replace(opaque_id, "[private mail item]")
        return redacted
    if isinstance(value, list):
        return [_redact_mail_provider_ids(item, opaque_ids) for item in value]
    if isinstance(value, dict):
        return {
            key: _redact_mail_provider_ids(item, opaque_ids)
            for key, item in value.items()
        }
    return value


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
    mail_opaque_ids = _mail_opaque_provider_ids(mail)

    def safe_mail_fact(value: Any) -> Any:
        return _redact_mail_provider_ids(value, mail_opaque_ids)

    add(
        "packet.superhuman.summary",
        "mail_coverage",
        safe_mail_fact(
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
            safe_mail_fact(
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
    category_index = (
        mail.get("category_index")
        if isinstance(mail.get("category_index"), dict)
        else {}
    )
    for category in MAIL_ACTION_CATEGORIES:
        receipt = (
            category_index.get(category)
            if isinstance(category_index.get(category), dict)
            else {}
        )

        def count_or_unknown(key: str) -> int | None:
            value = receipt.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
            return None

        add(
            f"packet.superhuman.category_index.{category}",
            "mail_population",
            {
                "category": category,
                "total": count_or_unknown("total"),
                "shown": count_or_unknown("shown"),
                "omitted": count_or_unknown("omitted"),
                "locations_complete": receipt.get("locations_complete") is True,
            },
        )

        rows = mail.get(category) if isinstance(mail.get(category), list) else []
        for index, row in enumerate(rows[: caps["mail_candidates_per_kind"]]):
            add(
                f"packet.superhuman.{category}.{index}",
                "mail_candidate",
                safe_mail_fact(
                    _bounded_dict(
                        row,
                        (
                            "subject",
                            "last_message_at",
                            "source_identities",
                            "action_tags",
                            "semantic_status",
                            "confidence",
                            "source_observed_at",
                            "message_age_hours",
                            "waiting_direction",
                            "proposal",
                            "wake",
                        ),
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
        snowcubes.get("surfaces") if isinstance(snowcubes.get("surfaces"), list) else []
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


def build_customer_evidence_projection(
    packet: dict[str, Any],
    profile: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project exact two-source customer facts without ranking or prose."""
    if not isinstance(packet, dict):
        raise AuthoringError("source packet must be a JSON object")
    source = packet.get("snowcubes_customer_opportunities")
    if not isinstance(source, dict):
        source = {
            "status": "UNKNOWN",
            "source_status": {"superhuman": "UNAVAILABLE", "shopify": "UNAVAILABLE"},
            "opportunities": [],
            "problems": ["customer-opportunity source is absent"],
            "no_write_receipt": {
                "provider_calls": 0,
                "drafts_created": 0,
                "messages_sent": 0,
                "shopify_mutations": 0,
            },
        }
    receipt = source.get("no_write_receipt")
    expected_receipt = {
        "provider_calls": 0,
        "drafts_created": 0,
        "messages_sent": 0,
        "shopify_mutations": 0,
    }
    if receipt != expected_receipt:
        raise AuthoringError(
            "customer-opportunity source lacks an exact no-write receipt"
        )

    source_status = source.get("source_status")
    if not isinstance(source_status, dict):
        source_status = {"superhuman": "UNAVAILABLE", "shopify": "UNAVAILABLE"}
    problems = [
        str(value)[:400]
        for value in (source.get("problems") or [])
        if isinstance(value, str) and value.strip()
    ]
    if source.get("schema") != "shadow.snowcubes-customer-opportunities.v1":
        problems.append("customer-opportunity source schema is unsupported")
    packet_time: datetime | None = None
    try:
        packet_time = datetime.fromisoformat(
            str(packet.get("generated_at") or "").replace("Z", "+00:00")
        )
        source_time = datetime.fromisoformat(
            str(source.get("observed_at") or "").replace("Z", "+00:00")
        )
        if packet_time.tzinfo is None or source_time.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            raise ValueError("current time must include a timezone")
        packet_age_hours = (current_time - packet_time).total_seconds() / 3600.0
        source_age_hours = (packet_time - source_time).total_seconds() / 3600.0
        if (
            packet_age_hours < 0
            or packet_age_hours > profile["max_source_age_hours"]
            or source_age_hours < 0
            or source_age_hours > profile["max_source_age_hours"]
        ):
            problems.append(
                "customer-opportunity source observation is stale or future-dated"
            )
    except ValueError:
        problems.append("customer-opportunity source observation time is invalid")
    by_id: dict[str, dict[str, Any]] = {}
    collisions: set[str] = set()
    for raw in source.get("opportunities") or []:
        if not isinstance(raw, dict):
            problems.append("customer-opportunity source contains a malformed row")
            continue
        opportunity_id = str(raw.get("opportunity_id") or "").strip()
        if not opportunity_id:
            problems.append("customer-opportunity row lacks a stable identity")
            continue
        clean = _sanitize_fact(raw)
        prior = by_id.get(opportunity_id)
        if prior is None:
            by_id[opportunity_id] = clean
        elif canonical_json(prior) != canonical_json(clean):
            collisions.add(opportunity_id)
            problems.append(
                f"conflicting duplicate customer-opportunity identity: {opportunity_id}"
            )
    for opportunity_id in collisions:
        by_id.pop(opportunity_id, None)

    stable_owners: dict[tuple[str, str], str] = {}
    for opportunity_id, row in by_id.items():
        if not isinstance(row, dict):
            continue
        identity = row.get("customer_identity")
        mail = row.get("mail")
        shopify = row.get("shopify")
        stable_ids = {
            "shopify_customer": (
                identity.get("shopify_customer_id")
                if isinstance(identity, dict)
                else None
            ),
            "superhuman_thread": mail.get("thread_id")
            if isinstance(mail, dict)
            else None,
            "shopify_order": shopify.get("order_id")
            if isinstance(shopify, dict)
            else None,
        }
        for kind, provider_id in stable_ids.items():
            if not isinstance(provider_id, str) or not provider_id:
                continue
            key = (kind, provider_id)
            prior = stable_owners.get(key)
            if prior is None:
                stable_owners[key] = opportunity_id
            elif prior != opportunity_id:
                problems.append(
                    f"customer-opportunity provider identity is reused across rows: {kind}:{provider_id}"
                )

    facts: list[dict[str, Any]] = []
    eligible_ids: list[str] = []
    for opportunity_id in sorted(by_id)[: profile["opportunity_cap"]]:
        row = by_id[opportunity_id]
        if not isinstance(row, dict):
            continue
        identity = row.get("customer_identity")
        mail = row.get("mail")
        shopify = row.get("shopify")
        customer_id = (
            identity.get("shopify_customer_id") if isinstance(identity, dict) else None
        )
        mail_provider_key = mail.get("provider_key") if isinstance(mail, dict) else None
        shopify_provider_key = (
            shopify.get("provider_key") if isinstance(shopify, dict) else None
        )
        identity_email = (
            identity.get("customer_email") if isinstance(identity, dict) else None
        )
        mail_email = mail.get("customer_email") if isinstance(mail, dict) else None
        shopify_email = (
            shopify.get("customer_email") if isinstance(shopify, dict) else None
        )
        row_times_valid = True
        for value in (
            mail.get("observed_at") if isinstance(mail, dict) else None,
            shopify.get("observed_at") if isinstance(shopify, dict) else None,
        ):
            try:
                parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
                if parsed.tzinfo is None or packet_time is None or parsed > packet_time:
                    row_times_valid = False
            except ValueError:
                row_times_valid = False
        confidence_by_basis = {
            "exact_order_id": "HIGH",
            "exact_order_name": "HIGH",
            "exact_customer_id": "HIGH",
            "exact_verified_email": "MEDIUM",
        }
        eligible = bool(
            source.get("status") == "COMPLETE"
            and row.get("join_state") == "MATCHED"
            and row.get("match_basis") in confidence_by_basis
            and row.get("confidence") == confidence_by_basis.get(row.get("match_basis"))
            and isinstance(identity, dict)
            and identity.get("state") == "KNOWN"
            and isinstance(customer_id, str)
            and customer_id
            and isinstance(mail, dict)
            and isinstance(mail.get("thread_id"), str)
            and mail.get("thread_id")
            and isinstance(mail_provider_key, str)
            and mail_provider_key
            == f"superhuman:{profile['expected_mail_account']}:{mail.get('thread_id')}"
            and isinstance(shopify, dict)
            and isinstance(shopify.get("order_id"), str)
            and shopify.get("order_id")
            and isinstance(shopify_provider_key, str)
            and shopify_provider_key
            == f"shopify:{profile['expected_shopify_store']}:{shopify.get('order_id')}"
            and shopify.get("shopify_customer_id") == customer_id
            and (identity_email is None or identity_email == shopify_email)
            and (
                mail_email is None
                or shopify_email is None
                or mail_email == shopify_email
            )
            and row_times_valid
            and row.get("protected_action") == "PROPOSAL_ONLY"
            and row.get("permission_to_contact") == "UNKNOWN"
            and row.get("inventory_state") == "UNKNOWN"
        )
        if not eligible:
            if source.get("status") == "COMPLETE":
                problems.append(
                    f"customer-opportunity row is not an exact two-source join: {opportunity_id}"
                )
            continue
        eligible_ids.append(opportunity_id)
        prefix = f"packet.snowcubes_customer_opportunities.{opportunity_id}"
        facts.append(
            {
                "ref": f"{prefix}.customer",
                "kind": "customer_fact",
                "fact": {
                    "opportunity_id": opportunity_id,
                    "customer_identity": identity,
                    "join_state": row.get("join_state"),
                    "match_basis": row.get("match_basis"),
                    "confidence": row.get("confidence"),
                },
            }
        )
        facts.append(
            {
                "ref": f"{prefix}.mail",
                "kind": "mail_fact",
                "fact": {
                    "opportunity_id": opportunity_id,
                    **_bounded_dict(
                        mail,
                        (
                            "provider_key",
                            "thread_id",
                            "last_message_id",
                            "subject",
                            "observed_at",
                            "age_hours",
                            "confidence",
                            "semantic_status",
                            "waiting_direction",
                            "action_tags",
                            "shopify_order_name",
                            "shopify_customer_id",
                            "customer_email",
                        ),
                    ),
                },
            }
        )
        facts.append(
            {
                "ref": f"{prefix}.shopify",
                "kind": "shopify_fact",
                "fact": {
                    "opportunity_id": opportunity_id,
                    **_bounded_dict(
                        shopify,
                        (
                            "provider_key",
                            "order_id",
                            "order_name",
                            "shopify_customer_id",
                            "customer_email",
                            "created_at",
                            "observed_at",
                            "age_hours",
                            "customer_order_count",
                            "fulfillment_status",
                            "delivery_status",
                            "delivered_at",
                        ),
                    ),
                },
            }
        )
        facts.append(
            {
                "ref": f"{prefix}.signals",
                "kind": "opportunity_signals",
                "fact": {
                    "opportunity_id": opportunity_id,
                    "signals": row.get("signals"),
                    "permission_to_contact": "UNKNOWN",
                    "inventory_state": "UNKNOWN",
                    "protected_action": "PROPOSAL_ONLY",
                },
            }
        )

    projection_status = (
        "COMPLETE"
        if source.get("status") == "COMPLETE"
        and source_status.get("superhuman") == "COMPLETE"
        and source_status.get("shopify") == "COMPLETE"
        and not problems
        and not collisions
        else "UNKNOWN"
    )
    summary = {
        "status": projection_status,
        "source_status": _sanitize_fact(source_status),
        "observed_at": source.get("observed_at"),
        "problems": list(dict.fromkeys(problems)),
        "eligible_opportunity_ids": eligible_ids
        if projection_status == "COMPLETE"
        else [],
        "no_write_receipt": expected_receipt,
    }
    return {
        "schema": CUSTOMER_EVIDENCE_SCHEMA,
        "generated_at": packet.get("generated_at"),
        "source_packet_sha256": sha256_json(packet),
        "summary": summary,
        "facts": facts if projection_status == "COMPLETE" else [],
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


def _validate_cited_text(
    value: Any,
    *,
    field: str,
    known_refs: set[str],
    max_length: int,
) -> tuple[str, list[str]]:
    if not isinstance(value, dict) or set(value) != {"text", "source_refs"}:
        raise AuthoringError(f"customer-opportunity {field} is invalid")
    text = value.get("text")
    refs = value.get("source_refs")
    if not isinstance(text, str) or not text.strip() or len(text) > max_length:
        raise AuthoringError(f"customer-opportunity {field} prose is invalid")
    if (
        not isinstance(refs, list)
        or not refs
        or len(refs) != len(set(refs))
        or any(not isinstance(ref, str) or ref not in known_refs for ref in refs)
    ):
        raise AuthoringError(f"customer-opportunity {field} cites unknown evidence")
    return text.strip(), refs


def validate_customer_letter(
    letter: Any,
    evidence: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(letter, dict):
        raise AuthoringError("customer-opportunity model result must be a JSON object")
    if set(letter) != {"schema", "status", "ranked_opportunities", "exact_wake"}:
        raise AuthoringError("customer-opportunity model result fields are invalid")
    if letter.get("schema") != CUSTOMER_LETTER_SCHEMA:
        raise AuthoringError("customer-opportunity model result schema is unsupported")
    status = letter.get("status")
    rows = letter.get("ranked_opportunities")
    wake = letter.get("exact_wake")
    if status not in {"READY", "CLEAR", "UNKNOWN"}:
        raise AuthoringError("customer-opportunity status is invalid")
    if not isinstance(rows, list) or len(rows) > profile["opportunity_cap"]:
        raise AuthoringError("customer-opportunity ranking exceeds its cap")
    summary = (
        evidence.get("summary") if isinstance(evidence.get("summary"), dict) else {}
    )
    if summary.get("status") != "COMPLETE":
        if status != "UNKNOWN" or rows:
            raise AuthoringError(
                "incomplete customer sources must produce an empty UNKNOWN result"
            )
        if not isinstance(wake, str) or not wake.strip() or len(wake) > 600:
            raise AuthoringError(
                "UNKNOWN customer-opportunity result needs an exact wake"
            )
        if re.search(r"\b(?:send|email|draft|refund|purchase)\b", wake, re.I):
            raise AuthoringError(
                "UNKNOWN customer-opportunity wake crosses a protected boundary"
            )
        source_status = (
            summary.get("source_status")
            if isinstance(summary.get("source_status"), dict)
            else {}
        )
        missing_patterns = {
            "superhuman": r"\b(?:superhuman|mail|mailbox)\b",
            "shopify": r"\bshopify\b",
        }
        for provider, pattern in missing_patterns.items():
            if source_status.get(provider) != "COMPLETE" and not re.search(
                pattern, wake, re.I
            ):
                raise AuthoringError(
                    f"UNKNOWN customer-opportunity wake does not name missing {provider}"
                )
        return letter

    eligible_ids = set(summary.get("eligible_opportunity_ids") or [])
    if not eligible_ids:
        if status != "CLEAR" or rows or wake is not None:
            raise AuthoringError("complete empty customer evidence must produce CLEAR")
        return letter
    if status != "READY" or not rows or wake is not None:
        raise AuthoringError("eligible customer evidence must produce a READY ranking")

    facts = evidence.get("facts") if isinstance(evidence.get("facts"), list) else []
    known_refs = {
        row.get("ref")
        for row in facts
        if isinstance(row, dict) and isinstance(row.get("ref"), str)
    }
    ref_to_opportunity: dict[str, str] = {}
    allowed_provenance: dict[tuple[str, str, str], str] = {}
    for row in facts:
        if not isinstance(row, dict) or not isinstance(row.get("fact"), dict):
            continue
        ref = row.get("ref")
        fact = row["fact"]
        opportunity_id = fact.get("opportunity_id")
        if not isinstance(ref, str) or not isinstance(opportunity_id, str):
            continue
        ref_to_opportunity[ref] = opportunity_id
        if row.get("kind") == "customer_fact":
            identity = fact.get("customer_identity")
            provider_id = (
                identity.get("shopify_customer_id")
                if isinstance(identity, dict)
                else None
            )
            if isinstance(provider_id, str) and provider_id:
                allowed_provenance[(ref, "shopify_customer", provider_id)] = (
                    opportunity_id
                )
        elif row.get("kind") == "mail_fact":
            provider_id = fact.get("thread_id")
            if isinstance(provider_id, str) and provider_id:
                allowed_provenance[(ref, "superhuman_thread", provider_id)] = (
                    opportunity_id
                )
        elif row.get("kind") == "shopify_fact":
            provider_id = fact.get("order_id")
            if isinstance(provider_id, str) and provider_id:
                allowed_provenance[(ref, "shopify_order", provider_id)] = opportunity_id

    seen_ids: set[str] = set()
    reader_text: list[str] = []
    for row in rows:
        expected_fields = {
            "why_now",
            "customer_order_thread_provenance",
            "recommended_next_step",
            "draft_ready_factual_context",
        }
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise AuthoringError("ranked customer-opportunity item fields are invalid")
        provenance = row.get("customer_order_thread_provenance")
        if not isinstance(provenance, list) or len(provenance) != 3:
            raise AuthoringError(
                "customer-opportunity provenance must name customer, order, and thread"
            )
        provenance_ids: set[str] = set()
        provenance_kinds: set[str] = set()
        for item in provenance:
            if not isinstance(item, dict) or set(item) != {
                "source_ref",
                "provider",
                "provider_id",
            }:
                raise AuthoringError("customer-opportunity provenance item is invalid")
            key = (item["source_ref"], item["provider"], item["provider_id"])
            opportunity_id = allowed_provenance.get(key)
            if opportunity_id is None:
                raise AuthoringError(
                    "customer-opportunity provenance is not exact evidence"
                )
            provenance_ids.add(opportunity_id)
            provenance_kinds.add(item["provider"])
        if (
            provenance_kinds
            != {
                "shopify_customer",
                "shopify_order",
                "superhuman_thread",
            }
            or len(provenance_ids) != 1
        ):
            raise AuthoringError(
                "customer-opportunity provenance mixes provider identities"
            )
        opportunity_id = next(iter(provenance_ids))
        if opportunity_id not in eligible_ids or opportunity_id in seen_ids:
            raise AuthoringError(
                "customer-opportunity ranking repeats or invents an identity"
            )
        seen_ids.add(opportunity_id)

        why_text, why_refs = _validate_cited_text(
            row.get("why_now"),
            field="why now",
            known_refs=known_refs,
            max_length=420,
        )
        next_text, next_refs = _validate_cited_text(
            row.get("recommended_next_step"),
            field="recommended next step",
            known_refs=known_refs,
            max_length=420,
        )
        if any(
            re.search(r"\b(?:send|email|draft|refund|purchase)\b", text, re.I)
            for text in (why_text, next_text)
        ):
            raise AuthoringError(
                "customer-opportunity next step crosses a protected boundary"
            )
        context = row.get("draft_ready_factual_context")
        if not isinstance(context, list) or not context or len(context) > 8:
            raise AuthoringError("customer-opportunity factual context is invalid")
        all_refs = list(why_refs) + list(next_refs)
        reader_text.extend((why_text, next_text))
        for item in context:
            context_text, context_refs = _validate_cited_text(
                item,
                field="draft-ready factual context",
                known_refs=known_refs,
                max_length=320,
            )
            if re.match(
                r"\s*(?:subject:|dear\b|hi\b|hello\b|hey\b|best,|thanks,)",
                context_text,
                re.I,
            ):
                raise AuthoringError(
                    "customer-opportunity context contains draft prose"
                )
            if re.search(
                r"\b(?:send|email|draft|refund|purchase)\b", context_text, re.I
            ):
                raise AuthoringError(
                    "customer-opportunity context crosses a protected boundary"
                )
            reader_text.append(context_text)
            all_refs.extend(context_refs)
        if any(ref_to_opportunity.get(ref) != opportunity_id for ref in all_refs):
            raise AuthoringError(
                "customer-opportunity item mixes evidence from another customer"
            )
    if len("\n".join(reader_text)) > profile["reader_max_characters"]:
        raise AuthoringError(
            "customer-opportunity result exceeds the reader character cap"
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
        raise AuthoringError(
            "authored artifact host receipt does not bind its evidence"
        )
    letter = validate_letter(artifact.get("letter"), evidence, profile)
    if receipt.get("letter_sha256") != sha256_json(letter):
        raise AuthoringError("authored artifact host receipt does not bind its letter")
    return letter, evidence, receipt


def validate_customer_artifact(
    artifact: Any,
    profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if (
        not isinstance(artifact, dict)
        or artifact.get("schema") != CUSTOMER_ARTIFACT_SCHEMA
    ):
        raise AuthoringError("customer-opportunity artifact schema is unsupported")
    if set(artifact) != {"schema", "letter", "author_receipt", "evidence"}:
        raise AuthoringError("customer-opportunity artifact fields are invalid")
    evidence = artifact.get("evidence")
    receipt = artifact.get("author_receipt")
    if (
        not isinstance(evidence, dict)
        or evidence.get("schema") != CUSTOMER_EVIDENCE_SCHEMA
    ):
        raise AuthoringError("customer-opportunity artifact evidence is invalid")
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != CUSTOMER_RECEIPT_SCHEMA
        or receipt.get("status") != "ok"
        or receipt.get("evidence_sha256") != sha256_json(evidence)
    ):
        raise AuthoringError(
            "customer-opportunity host receipt does not bind its evidence"
        )
    host = receipt.get("host")
    if host not in profile["allowed_hosts"]:
        raise AuthoringError(
            "customer-opportunity host receipt names an unsupported host"
        )
    if receipt.get("profile_sha256") != sha256_json(profile):
        raise AuthoringError(
            "customer-opportunity host receipt does not bind its profile"
        )
    if (
        receipt.get("prompt_sha256")
        != hashlib.sha256(CUSTOMER_PROMPT_PATH.read_bytes()).hexdigest()
    ):
        raise AuthoringError(
            "customer-opportunity host receipt does not bind its prompt"
        )
    expected_tools = "read-only sandbox" if host == "codex" else False
    if receipt.get("tools_allowed") != expected_tools:
        raise AuthoringError(
            "customer-opportunity host receipt does not prove tool isolation"
        )
    try:
        generated_at = datetime.fromisoformat(
            str(evidence.get("generated_at") or "").replace("Z", "+00:00")
        )
        if generated_at.tzinfo is None:
            raise ValueError("timestamp lacks a timezone")
    except ValueError as exc:
        raise AuthoringError(
            "customer-opportunity artifact evidence time is invalid"
        ) from exc
    artifact_age = (datetime.now(timezone.utc) - generated_at).total_seconds() / 3600.0
    if artifact_age < 0 or artifact_age > profile["max_source_age_hours"]:
        raise AuthoringError("customer-opportunity artifact evidence is stale")
    letter = validate_customer_letter(artifact.get("letter"), evidence, profile)
    if receipt.get("letter_sha256") != sha256_json(letter):
        raise AuthoringError(
            "customer-opportunity host receipt does not bind its letter"
        )
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
                "<li><p>"
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
            "<li><code>"
            + html_lib.escape(ref)
            + "</code><span>"
            + html_lib.escape(fact)
            + "</span></li>"
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


def render_customer_letter_html(
    artifact: dict[str, Any], profile: dict[str, Any]
) -> str:
    letter, evidence, receipt = validate_customer_artifact(artifact, profile)
    used_refs: list[str] = []

    def cited(value: dict[str, Any]) -> str:
        for ref in value["source_refs"]:
            if ref not in used_refs:
                used_refs.append(ref)
        return f"<p>{html_lib.escape(value['text'])}</p>"

    cards: list[str] = []
    for index, row in enumerate(letter["ranked_opportunities"], start=1):
        provenance_items: list[str] = []
        for item in row["customer_order_thread_provenance"]:
            ref = item["source_ref"]
            if ref not in used_refs:
                used_refs.append(ref)
            label = {
                "shopify_customer": "Customer",
                "shopify_order": "Order",
                "superhuman_thread": "Thread",
            }[item["provider"]]
            provenance_items.append(
                f"<li><strong>{label}</strong><code>{html_lib.escape(item['provider_id'])}</code></li>"
            )
        context = "".join(
            f"<li>{cited(item)}</li>" for item in row["draft_ready_factual_context"]
        )
        cards.append(
            '<article class="opportunity">'
            f'<p class="rank">Priority {index}</p>'
            "<h2>Why now</h2>"
            + cited(row["why_now"])
            + '<h2>Customer · order · thread</h2><ul class="provenance">'
            + "".join(provenance_items)
            + "</ul><h2>Recommended next step</h2>"
            + cited(row["recommended_next_step"])
            + '<h2>Draft-ready factual context</h2><ul class="context">'
            + context
            + "</ul></article>"
        )

    status_copy = {
        "READY": "A short, source-backed review list is ready.",
        "CLEAR": "No source-backed customer opportunity needs review.",
        "UNKNOWN": "Customer opportunity ranking is unavailable.",
    }[letter["status"]]
    wake = (
        f'<section class="wake"><h2>Exact wake</h2><p>{html_lib.escape(letter["exact_wake"])}</p></section>'
        if letter["exact_wake"]
        else ""
    )
    fact_index = {
        row["ref"]: row
        for row in evidence.get("facts", [])
        if isinstance(row, dict) and isinstance(row.get("ref"), str)
    }
    appendix = "".join(
        "<li><code>"
        + html_lib.escape(ref)
        + "</code><span>"
        + html_lib.escape(
            json.dumps(fact_index[ref]["fact"], ensure_ascii=False, sort_keys=True)
        )
        + "</span></li>"
        for ref in used_refs
    )
    generated = html_lib.escape(str(evidence.get("generated_at") or "time unavailable"))
    host = html_lib.escape(str(receipt.get("host") or "model host unavailable"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Snowcubes customer opportunities</title>
<style>
:root {{ color-scheme:light; --ink:#231f1b; --muted:#746b62; --paper:#f4efe7; --card:#fffdf8; --line:#ddd3c8; --berry:#8f2445; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font-family:ui-sans-serif,system-ui,-apple-system,sans-serif; line-height:1.5; }}
main {{ width:min(820px,calc(100% - 32px)); margin:0 auto; padding:52px 0 72px; }}
.eyebrow,.rank,h2 {{ color:var(--berry); font-size:12px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }}
h1 {{ margin:8px 0 12px; max-width:18ch; font:500 clamp(34px,7vw,60px)/1.02 ui-serif,Georgia,serif; letter-spacing:-.035em; }}
.meta {{ margin:0 0 34px; color:var(--muted); font-size:14px; }}
.opportunity,.wake {{ margin:20px 0; padding:28px; background:var(--card); border:1px solid var(--line); border-radius:18px; box-shadow:0 12px 32px rgba(62,42,29,.05); }}
.rank {{ margin:0 0 18px; }} h2 {{ margin:22px 0 8px; }} p {{ margin:0; font-size:17px; }}
ul {{ margin:0; padding:0; list-style:none; }} .provenance {{ display:grid; gap:8px; }} .provenance li {{ display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; padding:10px 0; border-bottom:1px solid var(--line); }}
code {{ color:var(--muted); overflow-wrap:anywhere; }} .context li {{ padding:7px 0; }}
.context li::before {{ content:"•"; color:var(--berry); margin-right:9px; }}
details {{ margin-top:36px; color:var(--muted); font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace; }} summary {{ cursor:pointer; font-family:ui-sans-serif,system-ui,sans-serif; font-weight:700; color:var(--ink); }} details li {{ margin:12px 0; }} details code {{ display:block; color:var(--berry); }} details span {{ overflow-wrap:anywhere; }}
@media (max-width:520px) {{ main {{ width:min(100% - 22px,820px); padding:28px 0 44px; }} h1 {{ font-size:38px; }} .opportunity,.wake {{ padding:20px; border-radius:14px; }} .provenance li {{ display:block; }} .provenance code {{ display:block; margin-top:4px; }} }}
</style>
</head>
<body><main>
<p class="eyebrow">Private · Snowcubes</p>
<h1>{html_lib.escape(status_copy)}</h1>
<p class="meta">Observed {generated} · Authored by {host} · No draft or send</p>
{"".join(cards)}{wake}
<details><summary>Private source appendix · {len(used_refs)} cited facts</summary><ol>{appendix}</ol></details>
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
    if isinstance(envelope, dict) and isinstance(
        envelope.get("structured_output"), dict
    ):
        return envelope["structured_output"]
    if isinstance(envelope, dict) and isinstance(envelope.get("result"), str):
        return json.loads(envelope["result"])
    return envelope


def _invoke_structured_author(
    evidence: dict[str, Any],
    profile: dict[str, Any],
    *,
    host: str,
    result_schema_path: Path,
    prompt_path: Path,
    validator: Callable[[Any, dict[str, Any], dict[str, Any]], dict[str, Any]],
    receipt_schema: str,
    result_label: str,
    model: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    environ: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    executable = "codex" if host == "codex" else "claude"
    resolved = shutil.which(executable)
    if resolved is None:
        raise AuthoringError(f"configured author host is unavailable: {executable}")
    prompt = prompt_path.read_text(encoding="utf-8")
    prompt += (
        f"\n\nReturn only the schema-valid JSON {result_label} for this evidence:\n"
    )
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
                str(result_schema_path),
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
                raise AuthoringError(
                    f"codex author returned invalid JSON: {exc}"
                ) from exc
        else:
            schema = result_schema_path.read_text(encoding="utf-8")
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
                raise AuthoringError(
                    f"claude-code author returned invalid JSON: {exc}"
                ) from exc
    letter = validator(result, evidence, profile)
    receipt = {
        "schema": receipt_schema,
        "status": "ok",
        "host": host,
        "host_executable": resolved,
        "requested_model": model,
        "model_observed": None,
        "profile_sha256": sha256_json(profile),
        "prompt_sha256": hashlib.sha256(prompt_path.read_bytes()).hexdigest(),
        "evidence_sha256": sha256_json(evidence),
        "letter_sha256": sha256_json(letter),
        "authored_at": datetime.now(timezone.utc).isoformat(),
        "tools_allowed": False if host == "claude-code" else "read-only sandbox",
    }
    return letter, receipt


def invoke_author(
    evidence: dict[str, Any],
    profile: dict[str, Any],
    *,
    host: str,
    model: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    environ: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _invoke_structured_author(
        evidence,
        profile,
        host=host,
        result_schema_path=RESULT_SCHEMA_PATH,
        prompt_path=PROMPT_PATH,
        validator=validate_letter,
        receipt_schema=RECEIPT_SCHEMA,
        result_label="letter",
        model=model,
        runner=runner,
        environ=environ,
    )


def invoke_customer_author(
    evidence: dict[str, Any],
    profile: dict[str, Any],
    *,
    host: str,
    model: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    environ: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _invoke_structured_author(
        evidence,
        profile,
        host=host,
        result_schema_path=CUSTOMER_RESULT_SCHEMA_PATH,
        prompt_path=CUSTOMER_PROMPT_PATH,
        validator=validate_customer_letter,
        receipt_schema=CUSTOMER_RECEIPT_SCHEMA,
        result_label="customer-opportunity brief",
        model=model,
        runner=runner,
        environ=environ,
    )


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
    except (
        AuthoringError,
        OSError,
        ValueError,
        RecursionError,
        subprocess.TimeoutExpired,
    ) as exc:
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
        print(
            json.dumps({"status": "blocked", "wake": str(exc)}, indent=2),
            file=sys.stderr,
        )
        return 1
    print(str(output))
    return 0


def cmd_customer_project(args: argparse.Namespace) -> int:
    profile = load_customer_profile(Path(args.profile))
    packet = json.loads(Path(args.input).read_text(encoding="utf-8"))
    evidence = build_customer_evidence_projection(packet, profile)
    write_private_json(Path(args.output), evidence)
    print(args.output)
    return 0


def cmd_customer_author(args: argparse.Namespace) -> int:
    output = Path(args.output)
    try:
        profile = load_customer_profile(Path(args.profile))
        packet = json.loads(Path(args.input).read_text(encoding="utf-8"))
        evidence = build_customer_evidence_projection(packet, profile)
        host = resolve_host(profile, args.host, dict(os.environ))
        letter, receipt = invoke_customer_author(
            evidence,
            profile,
            host=host,
            model=args.model,
            environ=dict(os.environ),
        )
        artifact = {
            "schema": CUSTOMER_ARTIFACT_SCHEMA,
            "letter": letter,
            "author_receipt": receipt,
            "evidence": evidence,
        }
        write_private_json(output, artifact)
    except (
        AuthoringError,
        OSError,
        ValueError,
        RecursionError,
        subprocess.TimeoutExpired,
    ) as exc:
        blocked = {
            "schema": CUSTOMER_RECEIPT_SCHEMA,
            "status": "blocked",
            "wake": str(exc),
            "output_written": False,
        }
        print(json.dumps(blocked, indent=2), file=sys.stderr)
        return 1
    print(str(output))
    return 0


def cmd_customer_render(args: argparse.Namespace) -> int:
    try:
        profile = load_customer_profile(Path(args.profile))
        artifact = json.loads(Path(args.input).read_text(encoding="utf-8"))
        rendered = render_customer_letter_html(artifact, profile)
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
        print(
            json.dumps({"status": "blocked", "wake": str(exc)}, indent=2),
            file=sys.stderr,
        )
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
    for name, handler in (
        ("customer-project", cmd_customer_project),
        ("customer-author", cmd_customer_author),
    ):
        command = sub.add_parser(name)
        command.add_argument("--input", required=True)
        command.add_argument("--output", required=True)
        command.add_argument("--profile", default=str(CUSTOMER_PROFILE_PATH))
        if name == "customer-author":
            command.add_argument("--host", choices=("codex", "claude-code"))
            command.add_argument("--model")
        command.set_defaults(func=handler)
    customer_render = sub.add_parser("customer-render")
    customer_render.add_argument("--input", required=True)
    customer_render.add_argument("--output", required=True)
    customer_render.add_argument("--profile", default=str(CUSTOMER_PROFILE_PATH))
    customer_render.set_defaults(func=cmd_customer_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
