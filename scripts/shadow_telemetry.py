#!/usr/bin/env python3
"""Construct one closed local Shadow event shape without trusting its values."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final


SCHEMA: Final = "shadow.telemetry.event.v1"
EVENT_FIELDS: Final = (
    "schema",
    "recorded_at",
    "project",
    "entity",
    "row",
    "verb",
    "duration_ms",
    "outcome",
)


def event_record(candidate: Mapping[str, object]) -> dict[str, object]:
    """Project candidate data into the closed vocabulary; values stay untrusted."""
    return {
        "schema": SCHEMA,
        "recorded_at": candidate.get("recorded_at"),
        "project": candidate.get("project"),
        "entity": candidate.get("entity"),
        "row": candidate.get("row"),
        "verb": candidate.get("verb"),
        "duration_ms": candidate.get("duration_ms"),
        "outcome": candidate.get("outcome"),
    }
