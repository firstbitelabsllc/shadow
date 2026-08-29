"""Shared test-only installer for one canonical partitioned plan tree."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import shadow_plan_store as store  # noqa: E402


def install_plan_tree(root: Path, content: bytes, *, return_build: bool = False):
    build = store.build_tree(content)
    plan = root / "PLAN.md"
    plan.write_bytes(build.root_bytes)
    object_root = root / "PLAN.d" / "objects" / "sha256"
    for digest, body in build.objects.items():
        bucket = object_root / digest[:2]
        bucket.mkdir(parents=True, exist_ok=True)
        (bucket / digest).write_bytes(body)
    return (plan, build) if return_build else plan
