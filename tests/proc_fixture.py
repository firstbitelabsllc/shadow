"""Shared subprocess helpers for the test suite."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    """Run one git command in ``repo``; raise on failure, return stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env} if env else None,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def example_json(relative: str) -> dict:
    """Load one checked-in example document from the repository examples tree."""
    import json

    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "examples" / relative).read_text(encoding="utf-8"))
