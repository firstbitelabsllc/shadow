"""Canonical row IDs and read-only selectors derived from one entity plan."""

from __future__ import annotations

import re
from typing import Iterable, Mapping


ROW_ID_PATTERN = r"~[0-9a-z]{4}"
ROW_ID_RE = re.compile(rf"^{ROW_ID_PATTERN}$")
LEGACY_SELECTOR_PATTERN = r"[A-Za-z]+[0-9]*[a-z]?~[a-z0-9]+"
LEGACY_SELECTOR_RE = re.compile(rf"^{LEGACY_SELECTOR_PATTERN}$")
LEADING_LEGACY_SELECTOR_RE = re.compile(
    rf"^(?P<label>{LEGACY_SELECTOR_PATTERN})(?=\s|$)"
)
MAX_SELECTOR_CHARS = 80


class SelectorError(ValueError):
    """A selector is unsafe, missing, or ambiguous in its entity plan."""


def leading_legacy_selector(text: str) -> str | None:
    """Return the exact compatibility label at the start of row prose."""
    match = LEADING_LEGACY_SELECTOR_RE.match(text)
    return match.group("label") if match is not None else None


def valid_selector(selector: str) -> bool:
    """Selectors are either canonical IDs or bounded legacy labels."""
    return (
        0 < len(selector) <= MAX_SELECTOR_CHARS
        and (ROW_ID_RE.fullmatch(selector) is not None
             or LEGACY_SELECTOR_RE.fullmatch(selector) is not None)
    )


def resolve_row_selector(rows: Iterable[Mapping[str, str]], selector: str) -> str:
    """Resolve one exact selector to the canonical trailing ID in the plan."""
    materialized = list(rows)
    if ROW_ID_RE.fullmatch(selector) is not None:
        matches = [row["id"] for row in materialized if row.get("id") == selector]
    elif LEGACY_SELECTOR_RE.fullmatch(selector) is not None:
        matches = [
            row["id"]
            for row in materialized
            if leading_legacy_selector(row.get("text", "")) == selector
        ]
    else:
        raise SelectorError(
            "row selector must be a four-character ~hash or a leading legacy label "
            "like P9a~formats"
        )
    if not matches:
        raise SelectorError(f"no task carries selector {selector}")
    if len(matches) != 1:
        raise SelectorError(f"row selector {selector} is duplicated in the plan")
    canonical = matches[0]
    if ROW_ID_RE.fullmatch(canonical) is None:
        raise SelectorError(f"row selector {selector} does not resolve to one canonical id")
    return canonical


def alias_duplicates(rows: Iterable[Mapping[str, str]]) -> set[str]:
    """Legacy labels that would make a compatibility selector ambiguous."""
    counts: dict[str, int] = {}
    for row in rows:
        label = leading_legacy_selector(row.get("text", ""))
        if label is not None:
            counts[label] = counts.get(label, 0) + 1
    return {label for label, count in counts.items() if count > 1}
