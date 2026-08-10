"""The one canonical home of the secret- and private-path shapes.

Every runtime surface that refuses secret-shaped or machine-private values
imports from here. Focused scrub tests keep independent adversarial examples
that catch a weakened shape.
"""

from __future__ import annotations

import re
from typing import Final


PRIVATE_PATH_RE: Final = re.compile(
    r"(?:~/|/Users/|/home/|/private/var/|file:///|[A-Za-z]:[\\/]|\\\\)", re.IGNORECASE
)
SECRET_SHAPE_RE: Final = re.compile(
    r"(?:(?<![A-Za-z0-9])sk-(?:ant-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-/+=]{20,}|"
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----)",
    re.IGNORECASE,
)
