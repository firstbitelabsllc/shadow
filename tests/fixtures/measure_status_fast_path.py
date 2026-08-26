#!/usr/bin/env python3
"""Groundtruth fixture: an owned seat must outrun a delayed portfolio scan."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "scripts" / "shadow-status.py"
SPEC = importlib.util.spec_from_file_location("shadow_status_measure_fast_path", STATUS)
assert SPEC and SPEC.loader
status = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = status
SPEC.loader.exec_module(status)


PLAN = """# Owned

## Brief

- Project: owned
- Mode: ship

## Tasks

### Current work
- [in_progress] resume without portfolio delay ~aa11 | proof: cmd true
- [pending] accepted ~zz99 (DoD) | proof: cmd true | needs: ~aa11
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as dirname:
        root = Path(dirname)
        home = root / "home"
        home.mkdir()
        owned = root / "owned" / "PLAN.md"
        unrelated = root / "unrelated" / "PLAN.md"
        owned.parent.mkdir()
        unrelated.parent.mkdir()
        owned.write_text(PLAN, encoding="utf-8")
        unrelated.write_text(PLAN.replace("Owned", "Unrelated").replace("owned", "unrelated"), encoding="utf-8")
        payload = {
            "schema": "shadow.root-board.v1",
            "revision": 7,
            "projects": [
                {"id": "owned", "priority": 1},
                {"id": "unrelated", "priority": 2},
            ],
            "entities": [
                {"id": "a" * 64, "project": "owned", "plan": str(owned), "resume": "~aa11"},
                {"id": "b" * 64, "project": "unrelated", "plan": str(unrelated), "resume": "~aa11"},
            ],
            "claims": [{
                "entity": "a" * 64,
                "row": "~aa11",
                "owner": "codex",
                "claimed_at": "2026-08-26T00:00:00Z",
                "return_by": "2099-08-26T08:00:00Z",
                "recovery": "probe-proof-then-adopt-park-or-close",
            }],
        }
        calls = 0

        def delayed_portfolio(*args, **kwargs):
            nonlocal calls
            calls += 1
            time.sleep(2.25)
            return payload

        output = io.StringIO()
        started = time.monotonic()
        with (
            mock.patch.dict(os.environ, {"HOME": str(home)}),
            mock.patch.object(status._board, "snapshot", return_value=payload),
            mock.patch.object(status._import, "reconcile_portfolio", side_effect=delayed_portfolio),
            redirect_stdout(output),
            redirect_stderr(output),
        ):
            code = status.main(["--root", str(root), "--by", "codex"])
        elapsed = time.monotonic() - started

    if code != 0 or calls != 0 or elapsed >= 2.0:
        print(
            f"STATUS_FAST_PATH_FAIL code={code} reconcile_calls={calls} "
            f"elapsed={elapsed:.3f}s\n{output.getvalue()}",
            file=sys.stderr,
        )
        return 1
    print(
        f"STATUS_FAST_PATH_PASS code=0 reconcile_calls=0 elapsed={elapsed:.3f}s "
        "unrelated_plans=0 unrelated_remotes=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
