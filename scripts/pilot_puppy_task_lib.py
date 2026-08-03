#!/usr/bin/env python3
"""Read one frozen UTF-8 task through a bounded, non-symlink file descriptor."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


MAX_TASK_BYTES = 120_000


class TaskError(ValueError):
    """A caller supplied an unsafe or unreadable frozen task file."""


def read_frozen_task(value: str | Path) -> str:
    """Return one bounded UTF-8 task without a path check/read race.

    The descriptor is opened with ``O_NOFOLLOW`` where the platform supports
    it, checked with ``fstat``, and read incrementally. This prevents a later
    route packet from hashing bytes that a native host cannot safely read.
    """

    path = Path(value).expanduser()
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise TaskError("task file is unreadable") from None
    try:
        information = os.fstat(descriptor)
        if not stat.S_ISREG(information.st_mode):
            raise TaskError("task file must be a regular non-symlink file")
        if information.st_size > MAX_TASK_BYTES:
            raise TaskError("task file exceeds the bounded packet limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(8192, MAX_TASK_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_TASK_BYTES:
                raise TaskError("task file exceeds the bounded packet limit")
        payload = b"".join(chunks)
    except OSError:
        raise TaskError("task file is unreadable") from None
    finally:
        os.close(descriptor)
    try:
        task = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise TaskError("task file must be valid UTF-8") from None
    if not task.strip():
        raise TaskError("task file is empty")
    return task


def frozen_task_sha256(value: str | Path) -> tuple[str, str]:
    """Return exactly the text native hosts receive and its SHA-256 binding."""

    task = read_frozen_task(value)
    return task, hashlib.sha256(task.encode("utf-8")).hexdigest()
