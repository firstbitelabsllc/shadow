#!/usr/bin/env python3
"""Groundtruth fixture: an owned seat must outrun a delayed portfolio scan."""

from __future__ import annotations

import argparse
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


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--entities", type=int, default=25)
    result.add_argument("--remote-delay-ms", type=int, default=250)
    result.add_argument("--max-seconds", type=float, default=2.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.entities < 2 or args.remote_delay_ms < 0 or args.max_seconds <= 0:
        print("measurement arguments are outside the safe fixture bounds", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as dirname:
        root = Path(dirname)
        home = root / "home"
        home.mkdir()
        owned = root / "owned" / "PLAN.md"
        owned.parent.mkdir()
        owned.write_text(PLAN, encoding="utf-8")
        owned_id = status._board.entity_id(owned)
        projects = [{"id": "owned", "priority": 1}]
        entities = [
            {"id": owned_id, "project": "owned", "plan": str(owned), "resume": "~aa11"}
        ]
        for index in range(1, args.entities):
            project = f"unrelated-{index}"
            unrelated = root / project / "PLAN.md"
            unrelated.parent.mkdir()
            unrelated.write_text(
                PLAN.replace("Owned", project).replace("owned", project),
                encoding="utf-8",
            )
            projects.append({"id": project, "priority": index + 1})
            entities.append(
                {
                    "id": status._board.entity_id(unrelated),
                    "project": project,
                    "plan": str(unrelated),
                    "resume": "~aa11",
                }
            )
        payload = {
            "schema": "shadow.root-board.v1",
            "revision": 7,
            "projects": projects,
            "entities": entities,
            "claims": [{
                "entity": owned_id,
                "row": "~aa11",
                "owner": "codex",
                "claimed_at": "2026-08-26T00:00:00Z",
                "return_by": "2099-08-26T08:00:00Z",
                "recovery": "probe-proof-then-adopt-park-or-close",
            }],
        }
        reconcile_calls = 0
        remote_calls: list[str] = []
        reads: list[Path] = []
        real_read = status._board.read_plan_text

        def delayed_portfolio(*_call_args, **_call_kwargs):
            nonlocal reconcile_calls
            reconcile_calls += 1
            return payload

        def read(path: Path) -> str:
            reads.append(Path(path))
            return real_read(path)

        def delayed_remote(entity, project, plan_path, parsed, local_claims):
            remote_calls.append(entity["id"])
            time.sleep(args.remote_delay_ms / 1000)
            return list(local_claims), None

        output = io.StringIO()
        started = time.monotonic()
        with (
            mock.patch.dict(os.environ, {"HOME": str(home)}),
            mock.patch.object(status._board, "snapshot", return_value=payload),
            mock.patch.object(status._import, "reconcile_portfolio", side_effect=delayed_portfolio),
            mock.patch.object(status._board, "read_plan_text", side_effect=read),
            mock.patch.object(status, "projected_claims", side_effect=delayed_remote),
            redirect_stdout(output),
            redirect_stderr(output),
        ):
            code = status.main(["--root", str(root), "--by", "codex"])
        elapsed = time.monotonic() - started

    unrelated_reads = sum(path != owned for path in reads)
    unrelated_remotes = sum(entity != owned_id for entity in remote_calls)
    if (
        code != 0
        or reconcile_calls != 0
        or reads != [owned]
        or remote_calls != [owned_id]
        or elapsed >= args.max_seconds
    ):
        print(
            f"STATUS_FAST_PATH_FAIL code={code} reconcile_calls={reconcile_calls} "
            f"elapsed={elapsed:.3f}s unrelated_plans={unrelated_reads} "
            f"unrelated_remotes={unrelated_remotes}\n{output.getvalue()}",
            file=sys.stderr,
        )
        return 1
    print(
        f"STATUS_FAST_PATH_PASS code=0 reconcile_calls=0 elapsed={elapsed:.3f}s "
        f"entities={args.entities} unrelated_plans=0 unrelated_remotes=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
