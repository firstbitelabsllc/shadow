"""Shared Git identity and subprocess-environment boundary."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Final
from urllib.parse import unquote, urlsplit


GIT_INJECTION_VARS: Final = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_SYSTEM",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_NAMESPACE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
}


def _is_git_injection(name: str) -> bool:
    return name in GIT_INJECTION_VARS or re.fullmatch(
        r"GIT_CONFIG_(?:KEY|VALUE)_\d+", name
    ) is not None


def sanitized_git_env(
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return a Git environment that cannot redirect repository or config."""
    env = dict(os.environ)
    env.update(extra_env or {})
    for name in tuple(env):
        if _is_git_injection(name):
            env.pop(name)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "/usr/bin/false"
    return env


def sanitize_process_git_env() -> None:
    """Remove repository/config redirection without disabling normal auth."""
    for name in tuple(os.environ):
        if _is_git_injection(name):
            os.environ.pop(name)
    os.environ["GIT_NO_REPLACE_OBJECTS"] = "1"
    os.environ["GIT_TERMINAL_PROMPT"] = "0"


def normalized_origin(origin: str) -> str:
    """Return one offline identity for common Git remote spellings."""
    if not origin:
        return ""
    text = origin.strip()
    if "://" in text:
        parsed = urlsplit(text)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port == {"ssh": 22, "https": 443, "http": 80, "git": 9418}.get(scheme):
            port = None
        authority = host + (f":{port}" if port is not None else "")
        path = parsed.path.rstrip("/").removesuffix(".git")
        return authority + path
    text = text.split("#", 1)[0].split("?", 1)[0]
    text = text.rstrip("/").removesuffix(".git")
    text = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", text)
    text = re.sub(r"^[^/@]+@", "", text)
    text = re.sub(r"^([^/:]+):(?!/)", r"\1/", text)
    host, slash, path = text.partition("/")
    return host.lower() + slash + path


def local_git_identity(repo: Path, common_dir: str) -> str:
    """Return one identity shared by every worktree of a local repository."""
    common = Path(common_dir)
    if not common.is_absolute():
        common = repo / common
    return f"local-git:{common.resolve()}"


def transport_fingerprint(repo: Path, origin: str) -> tuple[str, ...]:
    """Return a private, conservative fetch/push transport identity."""
    raw = origin.strip()
    if raw.lower().startswith("file://"):
        parsed = urlsplit(raw)
        return ("file", str(Path(unquote(parsed.path)).resolve()))
    if "://" in raw:
        parsed = urlsplit(raw)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError:
            port = None
        default_port = {"ssh": 22, "https": 443, "http": 80, "git": 9418}.get(
            scheme
        )
        effective_port = port if port is not None else default_port
        ssh_user = unquote(parsed.username or "") if scheme == "ssh" else ""
        return (
            "url",
            scheme,
            ssh_user,
            host,
            str(effective_port or ""),
            parsed.path.rstrip("/").removesuffix(".git"),
            parsed.query,
            parsed.fragment,
        )
    scp = re.fullmatch(
        r"(?:(?P<user>[^/@:]+)@)?(?P<host>[^/:]+):(?P<path>[^/].*)",
        raw,
    )
    if scp is not None:
        return (
            "scp",
            scp.group("user") or "",
            scp.group("host").lower(),
            scp.group("path").rstrip("/").removesuffix(".git"),
        )
    local = Path(raw).expanduser()
    if not local.is_absolute():
        local = repo / local
    return ("file", str(local.resolve()))


def normalized_repo_origin(repo: Path, origin: str) -> str:
    """Normalize a configured remote, resolving filesystem forms at the repo."""
    raw = origin.strip()
    if not raw:
        return ""
    if raw.lower().startswith("file://"):
        parsed = urlsplit(raw)
        return f"local-remote:{Path(unquote(parsed.path)).resolve()}"
    if "://" in raw or re.match(r"^[^/@:]+@?[^/:]+:(?!/)", raw):
        return normalized_origin(raw)
    local = Path(raw).expanduser()
    if not local.is_absolute():
        local = repo / local
    return f"local-remote:{local.resolve()}"
