#!/usr/bin/env python3
"""One deterministic classifier for interpreter-backed cmd proofs."""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path


_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PYTHON = re.compile(r"^python(?:\d+(?:\.\d+)*)?$")


def _env_analysis(argv: list[str], depth: int = 0) -> tuple[list[str], str | None]:
    if depth >= 8:
        return [], "env wrapper nesting exceeds the supported proof-command depth"
    if not argv or Path(argv[0]).name != "env":
        return argv, None
    index = 1
    pending_issue: str | None = None
    while index < len(argv):
        token = argv[index]
        if token == "--":
            index += 1
            break
        if not token.startswith("-") and not _ASSIGNMENT.match(token):
            break
        if token in {"-C", "--chdir"} or token.startswith(("-C", "--chdir=")):
            pending_issue = "interpreter working directory cannot be changed with `env -C/--chdir`"
            index += 2 if token in {"-C", "--chdir"} else 1
            continue
        if token in {"-S", "--split-string"} or token.startswith("--split-string="):
            hidden = (
                argv[index + 1] if token in {"-S", "--split-string"} and index + 1 < len(argv)
                else token.split("=", 1)[1] if "=" in token else ""
            )
            try:
                hidden_argv = shlex.split(hidden)
            except ValueError:
                hidden_argv = []
            hidden_command, hidden_issue = (
                _env_analysis(["env", *hidden_argv], depth + 1) if hidden_argv else ([], None)
            )
            if hidden_command and _is_supported_interpreter(hidden_command[0]):
                return hidden_command, (
                    "interpreter argv cannot be hidden inside `env -S/--split-string`"
                )
            return hidden_command, hidden_issue
        if token in {"-u", "--unset"}:
            index += 2
            continue
        if token.startswith(("-u", "--unset=")) or token in {
            "-i", "--ignore-environment", "-0", "--null",
        } or _ASSIGNMENT.match(token):
            index += 1
            continue
        if token.startswith("-"):
            return [], None
        index += 1
    command, nested_issue = _env_analysis(argv[index:], depth + 1)
    if nested_issue:
        return command, nested_issue
    if command and _is_supported_interpreter(command[0]):
        return command, pending_issue
    return command, None


def _env_unsafe_mode(argv: list[str]) -> str | None:
    return _env_analysis(argv)[1]


def _is_supported_interpreter(program: str) -> bool:
    name = Path(program).name.lower()
    return bool(_PYTHON.fullmatch(name) or name in {"node", "nodejs"})


def _unwrap_env(argv: list[str]) -> list[str]:
    return _env_analysis(argv)[0]


def _first_operand(
    args: list[str],
    *,
    no_script_modes: set[str],
    terminal_modes: set[str],
    value_flags: set[str],
    joined_value_prefixes: tuple[str, ...],
) -> str | None:
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--":
            return args[index + 1] if index + 1 < len(args) else None
        if token in terminal_modes:
            return None
        if token in no_script_modes or any(
            token.startswith(mode + "=") or (
                mode.startswith("-") and not mode.startswith("--") and token.startswith(mode)
            )
            for mode in no_script_modes
        ):
            return None
        if token in value_flags:
            index += 2
            continue
        if any(token.startswith(prefix) and token != prefix for prefix in joined_value_prefixes):
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return None


def script_operand(argv: list[str]) -> str | None:
    """Return the repository script an interpreter will execute, if explicit.

    This is intentionally a small command grammar, not a scan for path-looking
    strings. Output paths and inline programs are not executable source files.
    """
    command = _unwrap_env(argv)
    if not command:
        return None
    name = Path(command[0]).name.lower()
    args = command[1:]

    if _PYTHON.fullmatch(name):
        return _first_operand(
            args,
            no_script_modes={"-c", "-m"},
            terminal_modes={"-h", "--help", "-V", "--version"},
            value_flags={"-W", "-X", "-Q", "--check-hash-based-pycs"},
            joined_value_prefixes=("-W", "-X", "-Q", "--check-hash-based-pycs="),
        )
    if name in {"node", "nodejs"}:
        return _first_operand(
            args,
            no_script_modes={"-e", "--eval", "-p", "--print"},
            terminal_modes={"-h", "--help", "-v", "--version"},
            value_flags={
                "-r", "--require", "--import", "--loader", "--conditions", "--input-type",
            },
            joined_value_prefixes=(
                "--require=", "--import=", "--loader=", "--conditions=", "--input-type=",
            ),
        )
    return None


def _is_regular_file_in_head(root: Path, relative: Path) -> bool:
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if top.returncode:
        return False
    git_root = Path(top.stdout.strip()).resolve()
    candidate = (root.resolve() / relative).resolve(strict=False)
    try:
        git_relative = candidate.relative_to(git_root)
    except ValueError:
        return False
    try:
        entry = subprocess.run(
            ["git", "-C", str(git_root), "ls-tree", "-z", "HEAD", "--", str(git_relative)],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if entry.returncode or not entry.stdout:
        return False
    metadata = entry.stdout.split(b"\t", 1)[0].split()
    return len(metadata) == 3 and metadata[0] in {b"100644", b"100755"} and metadata[1] == b"blob"


def script_operand_issue(argv: list[str], root: Path) -> str | None:
    """Explain why an explicit interpreter script is not clean-checkout source."""
    env_issue = _env_unsafe_mode(argv)
    if env_issue:
        return env_issue
    operand = script_operand(argv)
    if operand is None:
        return None
    relative = Path(operand)
    if relative.is_absolute():
        return f"interpreter script `{operand}` must be relative to its PLAN.md"
    canonical_root = root.resolve()
    candidate = (canonical_root / relative).resolve(strict=False)
    try:
        candidate.relative_to(canonical_root)
    except ValueError:
        return f"interpreter script `{operand}` escapes its PLAN.md directory"
    if not _is_regular_file_in_head(canonical_root, relative):
        return f"interpreter script `{operand}` is not a committed regular file beside its PLAN.md"
    return None
