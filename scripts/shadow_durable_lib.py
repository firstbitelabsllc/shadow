"""One durable single-file write contract: complete content or nothing."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_write(
    path: Path,
    payload: bytes,
    *,
    mode: int = 0o600,
    exclusive: bool = False,
    follow_symlinks: bool = True,
    make_parents: bool = False,
) -> None:
    """Write `payload` to `path` atomically: temp file, fsync, then one rename
    or one exclusive hard link, plus a directory fsync. A crash at any point
    leaves the complete old file or the complete new one, never a truncation.

    `exclusive=True` uses os.link so an existing destination fails with
    FileExistsError instead of being replaced. The temporary file is always
    removed. Errors from the filesystem propagate unchanged so callers map
    them onto their own domain types.
    """
    if make_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path, follow_symlinks=follow_symlinks)
        else:
            os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)
