"""One durable single-file write contract: complete content or nothing."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile


def fsync_directory(path: Path, *, best_effort: bool = False) -> None:
    """Flush a rename or link into the directory so the NAME change is durable.

    fsync on a file makes its bytes survive a crash; the directory entry —
    those bytes wearing this name — survives only when the parent directory is
    synced too. Without it a write is atomically visible but not durable: a
    crash right after the rename can lose the name change. `best_effort`
    tolerates filesystems that reject a directory fsync; the common case
    (APFS, ext4) makes the completed write crash-durable.
    """
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
    try:
        if best_effort:
            try:
                os.fsync(descriptor)
            except OSError:
                pass
        else:
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
        fsync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)
