"""Shared subprocess helpers for the test suite."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from scripts.shadow_git_fixture import configure_public_ssh_fixture


PUBLIC_FIXTURE_SSH_URL = "ssh://fixture@fixture.invalid/project.git"


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


def configure_public_fixture_ssh_remote(repo: Path, bare: Path) -> str:
    """Route one public SSH identity to a fixture bare repository.

    This is deliberately a Git SSH transport, rather than a file-URL alias:
    callers exercise Git's actual receive-pack/upload-pack CAS while repository
    binding observes only the fixed public endpoint.  The bridge accepts one
    service and one declared public repository path, then execs Git directly;
    it never invokes a shell or opens a network connection.
    """
    configure_public_ssh_fixture(
        repo, bare, public_url=PUBLIC_FIXTURE_SSH_URL,
        bridge_name="fixture-ssh-bridge.py",
    )
    return PUBLIC_FIXTURE_SSH_URL
