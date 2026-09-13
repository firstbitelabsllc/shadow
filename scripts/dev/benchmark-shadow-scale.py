#!/usr/bin/env python3
"""Synthetic native Shadow scaling measurements; never reads live plan content.

Example (run in the source checkout):
  SHADOW_SCALE_FIXTURE_ROOT=/absolute/scratch/scale python3 scripts/dev/benchmark-shadow-scale.py build
  SHADOW_SCALE_FIXTURE_ROOT=/absolute/scratch/scale python3 scripts/dev/benchmark-shadow-scale.py bench --repeats 5

SHADOW_SCALE_SOURCE selects an alternate checkout for a before/after run.
SHADOW_SCALE_LABEL disambiguates all result/profile artifacts. Use
SHADOW_SCALE_LABEL=baseline for the original source and SHADOW_SCALE_LABEL=after
with SHADOW_SCALE_SOURCE=/absolute/alternate/checkout for the repaired source.
Fixtures and result JSON remain in the supplied scratch root. Existing fixtures can be reused; supply
another root to create a clean fixture set. This is an opt-in measurement tool,
not a production gate or a claim that every operation scales by the same factor.
Native stdout and stderr are retained once per digest under outputs/sha256.
Use `build --mixed` and `bench --mixed` for the four-local/three-repository
mix; `retained` adds the separate retained-object and archive-directory corpora.

Only Path.home is redirected inside fixture child processes. Native parsers,
filesystem readers, Git, locks, journal, and CLI main functions remain real.
No HOME/USER/CODEX_HOME environment variable is reassigned.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import pstats
import re
import resource
import statistics
import subprocess
import sys
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

if not os.environ.get("SHADOW_SCALE_FIXTURE_ROOT"):
    raise SystemExit(
        "Set SHADOW_SCALE_FIXTURE_ROOT to a dedicated absolute scratch directory."
    )
LABEL = os.environ.get("SHADOW_SCALE_LABEL", "baseline")
if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", LABEL) is None:
    raise SystemExit("SHADOW_SCALE_LABEL must be a simple lowercase artifact label.")
HERE = Path(os.environ["SHADOW_SCALE_FIXTURE_ROOT"]).expanduser().resolve()
HERE.mkdir(parents=True, exist_ok=True)
SOURCE = Path(
    os.environ.get("SHADOW_SCALE_SOURCE", str(Path(__file__).resolve().parents[2]))
).resolve()
# A tracked source archive may omit tests. The fixture builder belongs to this
# driver; all native Shadow imports still resolve from the measured source first.
sys.path[:0] = [
    str(SOURCE),
    str(SOURCE / "scripts"),
    str(Path(__file__).resolve().parents[2]),
]
import shadow_plan_store as store
import shadow_root_board as board

# The shared test helper adds its own scripts directory during import. Restore
# source precedence before loading commands so alternate-source runs stay pinned.
native_import_path = list(sys.path)
from tests.plan_tree_fixture import install_plan_tree

sys.path[:] = native_import_path


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SOURCE / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


status = module("scale_native_status", "shadow-status.py")
reader = module("scale_native_read", "shadow-read.py")
lifecycle = module("scale_native_lifecycle", "shadow-lifecycle.py")

# Representative bounded hot-plan dimensions; every text, identity, owner
# and receipt below is synthetic. Grow entities and history, not the caps.
RECIPES = [
    (59817, 50, 8, False),
    (13770, 4, 1, True),
    (236556, 127, 32, True),
    (17018, 22, 5, False),
    (240159, 90, 20, True),
    (68794, 55, 10, True),
    (7281, 4, 1, False),
]


def ident(n):
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    for _ in range(4):
        out = digits[n % 36] + out
        n //= 36
    return "~" + out


def synthetic_text(project, target_bytes, rows, milestones, generation=0):
    parts = [
        f"# Synthetic {project}\n\n## Brief\n\n- Project: {project}\n- Mode: ship\n- Priority: 2\n\n",
        "## Tasks\n\n",
    ]
    offset = 0
    for m in range(milestones):
        count = rows // milestones + (m < rows % milestones)
        parts.append(f"### Deliver result {m:03}\n")
        ids = [ident(offset + i) for i in range(count)]
        for i, row in enumerate(ids):
            if i == count - 1:
                suffix = " | needs: " + ",".join(ids[:-1]) if len(ids) > 1 else ""
                parts.append(
                    f"- [pending] Result {m:03} is accepted {row} (DoD) | proof: cmd true{suffix}\n"
                )
            else:
                parts.append(
                    f"- [pending] Produce output {i:03} for result {m:03} {row} | proof: cmd true\n"
                )
        offset += count
        parts.append("\n")
    parts.append(
        f"## Progress\n\n- 2026-09-01T00:00:00Z NOTE generation {generation:08}\n"
    )
    text = "".join(parts)
    seq = 0
    while len(text.encode()) < target_bytes:
        lead = f"- 2026-09-01T00:00:00Z NOTE synthetic receipt {seq:04}: "
        remaining = target_bytes - len(text.encode())
        if remaining < len(lead) + 2:
            text += "\n" + "x" * max(0, remaining - 1)
            break
        line = lead + ("historical observation remains synthetic. " * 45)
        text += line[: min(1900, remaining - 1)] + "\n"
        seq += 1
    return text.encode()


@contextmanager
def fixture_home(home):
    home = Path(home).resolve()
    assert home.is_relative_to(HERE)
    with (
        patch.object(Path, "home", return_value=home),
        patch.dict(
            os.environ,
            {
                "SHADOW_PORTFOLIO_ROOT": str(home / "Development"),
                "SHADOW_DEV_ROOT": str(home / "Development"),
                "GIT_TERMINAL_PROMPT": "0",
                "SHADOW_TELEMETRY": "off",
            },
        ),
    ):
        yield


def seed_portfolio(multiplier, *, mixed=False):
    scenario = "mixed" if mixed else "local"
    home = HERE / f"portfolio-{'mixed-' if mixed else ''}{multiplier}n"
    if (home / "fixture.json").exists():
        return json.loads((home / "fixture.json").read_text())
    (home / "Development").mkdir(parents=True, exist_ok=True)
    entities = []
    claims = []
    projects = []
    dims = []
    with fixture_home(home):
        for group in range(multiplier):
            for p in range(5):
                projects.append({"id": f"synthetic-{group:02}-{p}", "priority": 2})
            for i, (size, rows, milestones, tree) in enumerate(RECIPES):
                index = group * 7 + i
                project = f"synthetic-{group:02}-{min(i, 4)}"
                repository = mixed and i in (1, 4, 5)
                root = (
                    home / "Development" / f"repository-{index:03}"
                    if repository
                    else home / ".shadow" / "plans" / f"entity-{index:03}"
                )
                root.mkdir(parents=True, exist_ok=True)
                content = synthetic_text(project, size, rows, milestones)
                measured = board.hot_plan_budget(content)
                assert measured["within_limits"], measured
                assert not [
                    f
                    for f in status._lint.lint_plan(content.decode())
                    if f["severity"] == "blocking"
                ]
                path = install_plan_tree(root, content) if tree else root / "PLAN.md"
                if not tree:
                    path.write_bytes(content)
                if repository:
                    for args in (
                        ["init", "--quiet"],
                        ["add", "--", "PLAN.md", "PLAN.d"],
                        [
                            "-c",
                            "user.name=Synthetic benchmark",
                            "-c",
                            "user.email=benchmark@example.invalid",
                            "-c",
                            "commit.gpgSign=false",
                            "-c",
                            "core.hooksPath=/dev/null",
                            "commit",
                            "--quiet",
                            "-m",
                            "Seed synthetic bounded plan",
                        ],
                    ):
                        subprocess.run(
                            ["git", "-C", str(root), *args],
                            check=True,
                            capture_output=True,
                        )
                identity = board.entity_id(path)
                entities.append(
                    {
                        "id": identity,
                        "project": project,
                        "plan": str(path),
                        "resume": "~0000",
                    }
                )
                if i in (0, 2, 4):
                    claims.append(
                        {
                            "entity": identity,
                            "row": "~0000",
                            "owner": f"seat-{index:03}",
                            "claimed_at": "2026-09-01T00:00:00Z",
                            "return_by": "2099-09-01T00:00:00Z",
                            "recovery": "probe-proof-then-adopt-park-or-close",
                        }
                    )
                dims.append({**measured, "tree": tree, "repository": repository})
        payload = {
            "schema": "shadow.root-board.v1",
            "revision": 100,
            "projects": projects,
            "entities": entities,
            "claims": claims,
        }
        board_path = home / ".shadow" / "board.json"
        board_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        board.ensure(home=home)
        assert len(board.snapshot(home=home)["entities"]) == 7 * multiplier
    result = {
        "home": str(home),
        "scenario": scenario,
        "entities": len(entities),
        "repository_authorities": sum(bool(x["repository"]) for x in dims),
        "local_authorities": sum(not x["repository"] for x in dims),
        "projects": len(projects),
        "claims": len(claims),
        "logical_bytes": sum(x["bytes"] for x in dims),
        "rows": sum(x["task_rows"] for x in dims),
        "milestones": sum(x["milestones"] for x in dims),
        "dimensions": dims,
        "first_tree_entity": entities[2]["id"],
        "board_bytes": board_path.stat().st_size,
    }
    (home / "fixture.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def seed_history(depth):
    root = HERE / f"history-{depth}"
    if (root / "fixture.json").exists():
        return json.loads((root / "fixture.json").read_text())
    root.mkdir(parents=True, exist_ok=True)
    previous = None
    oldest = None
    total_new_bytes = 0
    count = 0
    for generation in range(depth):
        content = synthetic_text("synthetic-history", 236556, 127, 32, generation)
        build = store.with_lineage(
            store.build_tree(content), generation=generation, previous_root=previous
        )
        if oldest is None:
            oldest = hashlib.sha256(content).hexdigest()
        for digest, body in {
            **build.objects,
            store.digest_bytes(build.root_bytes): build.root_bytes,
        }.items():
            path = root / "PLAN.d" / "objects" / "sha256" / digest[:2] / digest
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
                total_new_bytes += len(body)
                count += 1
        previous = store.digest_bytes(build.root_bytes)
    (root / "PLAN.md").write_bytes(build.root_bytes)
    result = {
        "plan": str(root / "PLAN.md"),
        "depth": depth,
        "logical_bytes": len(content),
        "oldest_logical_sha256": oldest,
        "root_sha256": previous,
        "objects": count,
        "object_bytes": total_new_bytes,
    }
    (root / "fixture.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def seed_retained(depth, target_objects, archives):
    """Add authentic unrelated retained blobs; never change the current root."""
    fixture = seed_history(depth)
    root = Path(fixture["plan"]).parent
    objects = root / "PLAN.d" / "objects" / "sha256"
    current = [path for path in objects.glob("*/*") if path.is_file()]
    for index in range(target_objects - len(current)):
        body = (
            f"- 2026-09-01T00:00:00Z NOTE retained synthetic receipt {index:08}: "
            + "An earlier synthetic observation remains retained. " * 128
            + "\n"
        ).encode()
        digest = store.digest_bytes(body)
        path = objects / digest[:2] / digest
        assert not path.exists(), (
            "use a fresh fixture or its completed retained receipt"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    archive_root = root / "docs" / "plan-archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    for index in range(archives):
        path = archive_root / f"archive-{index:05}.md"
        path.write_text(
            f"# Synthetic archive {index:05}\n\n"
            + "Historical synthetic receipt, retained outside the hot plan.\n" * 460
        )
    current = [path for path in objects.glob("*/*") if path.is_file()]
    archive_files = list(archive_root.glob("*.md"))
    assert len(current) == target_objects
    assert len(archive_files) == archives
    assert store.digest_bytes((root / "PLAN.md").read_bytes()) == fixture["root_sha256"]
    result = {
        "depth": depth,
        "objects": len(current),
        "object_bytes": sum(path.stat().st_size for path in current),
        "archives": len(archive_files),
        "archive_bytes": sum(path.stat().st_size for path in archive_files),
        "root_sha256": fixture["root_sha256"],
    }
    (root / "retained.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def invoke(kind, fixture):
    if kind == "history-row":
        return (
            store.PlanSnapshot.open(Path(fixture["plan"])).row("~0000").content.decode()
        )
    if kind.startswith("history"):
        wanted = fixture["oldest_logical_sha256"] if kind == "history" else "0" * 64
        return lifecycle.local_source_text(Path(fixture["plan"]), wanted)
    home = Path(fixture["home"])
    with fixture_home(home):
        if kind == "status-full":
            return status.main(["--json"])
        if kind == "status-owned":
            return status.main(["--by", "seat-000"])
        if kind == "status-cold":
            return status.main(["--by", "fresh-seat"])
        if kind == "read-row":
            return reader.main(
                ["--entity", fixture["first_tree_entity"], "--row", "~0000"]
            )
        if kind == "board-snapshot":
            return board.snapshot(home=home)
        if kind == "board-noop":
            return board.ensure(home=home)
    raise ValueError(kind)


def worker(kind, fixture_path, instrument=False, profile=False):
    benchmark_source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    native_source_sha256 = {
        relative: hashlib.sha256((SOURCE / relative).read_bytes()).hexdigest()
        for relative in (
            "scripts/shadow-status.py",
            "scripts/shadow-lifecycle.py",
            "scripts/shadow-accept.py",
            "scripts/shadow_root_board.py",
            "scripts/shadow_plan_store.py",
        )
    }
    fixture_bytes = Path(fixture_path).read_bytes()
    fixture = json.loads(fixture_bytes)
    fixture_target = Path(fixture.get("home") or fixture["plan"]).resolve()
    if not fixture_target.is_relative_to(HERE):
        raise ValueError("Measured fixture must remain inside the scratch root.")
    runtime = {"python": sys.version, "platform": platform.platform()}
    out = io.StringIO()
    err = io.StringIO()
    counters = {
        "safe_reads": 0,
        "safe_bytes": 0,
        "materializations": 0,
        "git_processes": 0,
        "lineage_reads": 0,
        "lineage_bytes": 0,
    }
    safe_read = store._safe_read
    materialize = store.PlanSnapshot.materialize
    popen = subprocess.Popen
    lineage_read = lifecycle.read_regular_bounded

    def counted_read(path, limit):
        result = safe_read(path, limit)
        counters["safe_reads"] += 1
        counters["safe_bytes"] += len(result)
        return result

    def counted_materialize(self):
        counters["materializations"] += 1
        return materialize(self)

    def counted_popen(args, *a, **k):
        if (
            isinstance(args, (list, tuple))
            and args
            and Path(str(args[0])).name == "git"
        ):
            counters["git_processes"] += 1
        return popen(args, *a, **k)

    def counted_lineage(path, limit, label):
        result = lineage_read(path, limit, label)
        counters["lineage_reads"] += 1
        counters["lineage_bytes"] += len(result)
        return result

    before = resource.getrusage(resource.RUSAGE_SELF)
    child_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    code = 0
    value = None
    error = None
    profiler = cProfile.Profile()
    with (
        redirect_stdout(out),
        redirect_stderr(err),
        patch.object(store, "_safe_read", counted_read if instrument else safe_read),
        patch.object(
            store.PlanSnapshot,
            "materialize",
            counted_materialize if instrument else materialize,
        ),
        patch.object(subprocess, "Popen", counted_popen if instrument else popen),
        patch.object(
            lifecycle,
            "read_regular_bounded",
            counted_lineage if instrument else lineage_read,
        ),
    ):
        try:
            if profile:
                profiler.enable()
            value = invoke(kind, fixture)
            if type(value) is int:
                code = value
        except Exception as exc:  # noqa: BLE001 - retain native refusal details in measurements
            code = 1
            error = f"{type(exc).__name__}: {exc}"
        finally:
            if profile:
                profiler.disable()
    elapsed = time.perf_counter() - started
    finished_at = datetime.now(timezone.utc).isoformat()
    after = resource.getrusage(resource.RUSAGE_SELF)
    child_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    raw = out.getvalue().encode()
    if isinstance(value, str):
        raw = value.encode()
    if isinstance(value, dict):
        raw = json.dumps(value, sort_keys=True).encode()

    def retain_output(content):
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("outputs") / "sha256" / digest[:2] / digest
        path = HERE / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != content:
                raise ValueError("Retained benchmark output digest mismatch.")
        else:
            path.write_bytes(content)
        return str(relative)

    stdout_path = retain_output(raw)
    stderr_bytes = err.getvalue().encode()
    stderr_path = retain_output(stderr_bytes)
    if profile:
        profile_text = io.StringIO()
        pstats.Stats(profiler, stream=profile_text).sort_stats("cumtime").print_stats(
            35
        )
        (
            HERE
            / f"profile-{LABEL}-{kind}-{fixture.get('entities', fixture.get('depth'))}.txt"
        ).write_text(profile_text.getvalue())
    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "benchmark_source_sha256": benchmark_source_sha256,
        "fixture_manifest_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "native_source_sha256": native_source_sha256,
        "runtime": runtime,
        "scenario": fixture.get(
            "scenario", "local" if "home" in fixture else "history"
        ),
        "kind": kind,
        "size": fixture.get("entities", fixture.get("depth")),
        "elapsed_ms": elapsed * 1000,
        "cpu_user_ms": (after.ru_utime - before.ru_utime) * 1000,
        "cpu_system_ms": (after.ru_stime - before.ru_stime) * 1000,
        "child_user_ms": (child_after.ru_utime - child_before.ru_utime) * 1000,
        "child_system_ms": (child_after.ru_stime - child_before.ru_stime) * 1000,
        "max_rss_bytes": after.ru_maxrss
        * (1024 if sys.platform.startswith("linux") else 1),
        "input_blocks": after.ru_inblock - before.ru_inblock,
        "output_blocks": after.ru_oublock - before.ru_oublock,
        "returncode": code,
        "error": error,
        "stdout_bytes": len(raw),
        "stdout_sha256": hashlib.sha256(raw).hexdigest(),
        "stdout_path": stdout_path,
        "stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
        "stderr_path": stderr_path,
        "stderr": err.getvalue(),
        "instrumented": instrument,
        **counters,
    }


def measure(kind, path, repeats):
    runs = []
    for i in range(repeats + 1):
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, str(__file__), "worker", kind, str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        item = json.loads(result.stdout)
        item["process_elapsed_ms"] = (time.perf_counter() - start) * 1000
        if i:
            runs.append(item)
    count = json.loads(
        subprocess.run(
            [
                sys.executable,
                str(__file__),
                "worker",
                kind,
                str(path),
                "--instrument",
                "--profile",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    keys = [
        "elapsed_ms",
        "process_elapsed_ms",
        "cpu_user_ms",
        "cpu_system_ms",
        "child_user_ms",
        "child_system_ms",
        "max_rss_bytes",
    ]
    summary = {
        key: {
            "p50": statistics.median(x[key] for x in runs),
            "p95": sorted(x[key] for x in runs)[math.ceil(0.95 * len(runs)) - 1],
        }
        for key in keys
    }
    return {
        "kind": kind,
        "size": runs[0]["size"],
        "repeats": repeats,
        "warmup": 1,
        "summary": summary,
        "instrumentation": count,
        "runs": runs,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "retained", "bench", "worker"])
    parser.add_argument("rest", nargs="*")
    parser.add_argument("--instrument", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--mixed",
        action="store_true",
        help="Use four local and three separate repository authorities per group.",
    )
    args = parser.parse_args()
    if args.action == "worker":
        print(
            json.dumps(
                worker(*args.rest, instrument=args.instrument, profile=args.profile)
            )
        )
        return
    if args.action == "retained":
        for depth, objects, archives in ((203, 3887, 25), (2030, 38870, 250)):
            print(json.dumps(seed_retained(depth, objects, archives)), flush=True)
        return
    if args.action == "build":
        for m in (1, 10):
            print(json.dumps(seed_portfolio(m, mixed=args.mixed)), flush=True)
        for depth in (14, 127, 128, 129, 140, 203, 2030):
            print(json.dumps(seed_history(depth)), flush=True)
        return
    results = []
    for m in (1, 10):
        path = HERE / f"portfolio-{'mixed-' if args.mixed else ''}{m}n" / "fixture.json"
        for kind in (
            "status-owned",
            "status-cold",
            "status-full",
            "read-row",
            "board-snapshot",
            "board-noop",
        ):
            result = measure(kind, path, args.repeats)
            results.append(result)
            print(
                json.dumps(
                    {
                        "kind": kind,
                        "size": result["size"],
                        "summary": result["summary"],
                        "returncode": result["runs"][0]["returncode"],
                        "error": result["runs"][0]["error"],
                    }
                ),
                flush=True,
            )
            (HERE / f"results-{LABEL}.json").write_text(
                json.dumps(results, indent=2) + "\n"
            )
    for depth in (14, 127, 128, 129, 140, 203, 2030):
        result = measure(
            "history", HERE / f"history-{depth}" / "fixture.json", args.repeats
        )
        results.append(result)
        print(
            json.dumps(
                {
                    "kind": "history",
                    "size": depth,
                    "summary": result["summary"],
                    "returncode": result["runs"][0]["returncode"],
                    "error": result["runs"][0]["error"],
                }
            ),
            flush=True,
        )
        (HERE / f"results-{LABEL}.json").write_text(
            json.dumps(results, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
