#!/usr/bin/env python3
"""One owner for reading the VERSION file, matching the launcher's grammar.

Before this, four Python readers took `splitlines()[0]` (naive first line),
one test stripped the whole file, and `bin/shadow` skipped blank and comment
lines with awk — three mutually incompatible grammars, so a VERSION file with
a trailing note made `shadow --version`, doctor, and the distribution test
disagree about the product's own version. This is the single Python reader;
its grammar is exactly the launcher's `awk 'NF && $1 !~ /^#/ { print; exit }'`:
the first non-empty, non-comment line, stripped, validated as bare semver.
"""

from __future__ import annotations

import re
from pathlib import Path

_SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


class VersionError(RuntimeError):
    """The VERSION file is missing, unreadable, or not bare semver."""


def read_version(root: Path) -> str:
    """Return the product version from `root/VERSION`, launcher-identical.

    Raises VersionError if the file is absent, holds no payload line, or the
    payload line is not exactly MAJOR.MINOR.PATCH — the same shape the
    release packager validates, kept in one place so no reader can drift.
    """
    try:
        text = (Path(root) / "VERSION").read_text(encoding="utf-8")
    except OSError as exc:
        raise VersionError(f"VERSION file cannot be read under {root}") from exc
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # the awk `NF && $1 !~ /^#/` skip: blanks and comments
        if _SEMVER.fullmatch(stripped) is None:
            raise VersionError(
                f"VERSION payload line {stripped!r} is not bare MAJOR.MINOR.PATCH"
            )
        return stripped
    raise VersionError(f"VERSION under {root} has no non-comment payload line")
