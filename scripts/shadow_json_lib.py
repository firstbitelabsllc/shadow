"""Canonical JSON text: one serialization for receipts and CLI output."""

from __future__ import annotations

import json
from typing import Any


def json_text(payload: Any) -> str:
    """Serialize `payload` in Shadow's canonical form: two-space indent, sorted
    keys, one trailing newline. Receipts are compared byte-wise (CAS, dry-run
    vs apply, journal vs receipt), so every writer uses exactly this shape."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
