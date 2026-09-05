"""Test-only public SSH transport for disposable bare Git fixtures."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Mapping


def configure_public_ssh_fixture(
    repo: Path, bare: Path, *, public_url: str, bridge_name: str,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Route one declared public SSH endpoint to one local bare fixture.

    The generated bridge has no shell or network path: it accepts only Git's
    upload/receive-pack command for the URL's exact path, then execs Git with
    the fixture bare repository.  Distinct public URLs require distinct bridge
    names so parallel fixture repositories cannot clobber each other.
    """
    from urllib.parse import urlsplit

    parsed = urlsplit(public_url)
    if parsed.scheme != "ssh" or parsed.hostname != "fixture.invalid" or not parsed.path:
        raise ValueError("fixture SSH URL must use fixture.invalid and one path")
    bridge = bare.parent / bridge_name
    bridge.write_text(
        "#!/usr/bin/env python3\n"
        "import os\nimport shlex\nimport sys\n"
        f"BARE = {str(bare)!r}\n"
        f"DECLARED_PATH = {parsed.path!r}\n"
        "try:\n    command = shlex.split(sys.argv[-1], posix=True)\n"
        "except ValueError:\n    raise SystemExit(126)\n"
        "if len(command) != 2 or command[0] not in {'git-upload-pack', 'git-receive-pack'}:\n"
        "    raise SystemExit(126)\n"
        "if command[1] != DECLARED_PATH:\n    raise SystemExit(126)\n"
        "os.execvp(command[0], [command[0], BARE])\n",
        encoding="utf-8",
    )
    bridge.chmod(0o755)
    for args in (
        ("config", "core.sshCommand", str(bridge)),
        ("config", "ssh.variant", "ssh"),
        ("remote", "set-url", "origin", public_url),
        ("remote", "set-url", "--push", "origin", public_url),
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, env=environment)
