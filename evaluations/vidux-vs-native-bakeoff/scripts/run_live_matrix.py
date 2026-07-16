#!/usr/bin/env python3
"""Run live empirical bake-off matrix (no simulation)."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"

ARMS = ["cursor_native", "claude_native", "codex_native", "current_vidux", "thin_vidux_kernel"]


def discover_fixtures(pilot_only: bool) -> list[str]:
    fixtures = sorted(p.stem for p in (BASE / "fixtures").glob("*.json") if p.stem != "template-fixture")
    if pilot_only:
        fixtures = [f for f in fixtures if f.startswith("pilot-")]
    else:
        manifest = BASE / "fixtures" / "full-manifest.json"
        if manifest.exists():
            fixtures = json.loads(manifest.read_text(encoding="utf-8"))
    return fixtures


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def prepare(fixture_id: str, arm: str, run_id: str, work_root: Path) -> Path:
    cmd = [
        "python3",
        str(SCRIPTS / "run_arm.py"),
        "--fixture-id",
        fixture_id,
        "--arm",
        arm,
        "--run-id",
        run_id,
        "--work-root",
        str(work_root),
        "--prepare",
    ]
    result = run_cmd(cmd, BASE)
    if result.returncode != 0:
        raise RuntimeError(f"prepare failed: {result.stderr}")
    payload = json.loads(result.stdout)
    return Path(payload["run_dir"])


def invoke(run_dir: Path, arm: str, skip_cursor: bool, timeout_sec: int) -> dict:
    cmd = [
        "python3",
        str(SCRIPTS / "invoke_live_runner.py"),
        str(run_dir),
        "--arm",
        arm,
        "--timeout-sec",
        str(timeout_sec),
    ]
    if skip_cursor and arm == "cursor_native":
        cmd.append("--skip-cursor")
    result = run_cmd(cmd, BASE)
    if result.returncode != 0:
        raise RuntimeError(f"invoke failed: {result.stderr}")
    return json.loads(result.stdout)


def finalize(fixture_id: str, arm: str, run_id: str, work_root: Path) -> dict:
    cmd = [
        "python3",
        str(SCRIPTS / "run_arm.py"),
        "--fixture-id",
        fixture_id,
        "--arm",
        arm,
        "--run-id",
        run_id,
        "--work-root",
        str(work_root),
        "--finalize",
    ]
    result = run_cmd(cmd, BASE)
    if result.returncode != 0:
        raise RuntimeError(f"finalize failed: {result.stderr}")
    run_dir = work_root / run_id
    return json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))


def score_run(run_dir: Path) -> list[dict]:
    cmd = ["python3", str(SCRIPTS / "build_reviewer_packet.py"), str(run_dir)]
    result = run_cmd(cmd, BASE)
    if result.returncode != 0:
        raise RuntimeError(f"reviewer scoring failed: {result.stderr}")
    return json.loads((run_dir / "reviewer_scores.json").read_text(encoding="utf-8"))


def run_one(
    fixture_id: str,
    arm: str,
    run_id: str,
    work_root: Path,
    skip_cursor: bool,
    timeout_sec: int,
    finalize_only: bool = False,
) -> dict | None:
    run_dir = work_root / run_id
    if not finalize_only:
        prepare(fixture_id, arm, run_id, work_root)
        runner = invoke(run_dir, arm, skip_cursor, timeout_sec)
        if runner.get("status") == "AWAITING_AGENT":
            return None
    if not (run_dir / "runner_result.json").exists() and arm == "cursor_native":
        return None
    metrics = finalize(fixture_id, arm, run_id, work_root)
    score_run(run_dir)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--results-dir", default=str(BASE / "results" / "live"))
    parser.add_argument("--work-root", default=str(BASE / "runs" / "live"))
    parser.add_argument("--skip-cursor", action="store_true", help="leave cursor runs awaiting in-session agent")
    parser.add_argument("--arms", help="comma-separated arm filter")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--finalize-pending-cursor", action="store_true")
    parser.add_argument("--resume", action="store_true", help="skip runs already in raw-runs.jsonl; do not wipe results")
    parser.add_argument("--timeout-sec", type=int, default=5400)
    parser.add_argument("--max-runs", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve()
    work_root = Path(args.work_root).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)

    fixtures = discover_fixtures(args.pilot_only)
    arms = ARMS
    if args.arms:
        arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    pairs = [(f, a) for f in fixtures for a in arms]
    rng = random.Random(args.seed)
    rng.shuffle(pairs)

    randomization_path = results_dir / "randomization.json"
    if randomization_path.exists() and args.finalize_pending_cursor:
        pairs = [tuple(x.values()) for x in json.loads(randomization_path.read_text())["order"]]
    else:
        (randomization_path).write_text(
            json.dumps({"seed": args.seed, "mode": "live", "order": [{"fixture_id": f, "arm": a} for f, a in pairs]}, indent=2)
            + "\n",
            encoding="utf-8",
        )

    raw_path = results_dir / "raw-runs.jsonl"
    scores_path = results_dir / "reviewer-scores.jsonl"
    completed_ids: set[str] = set()
    if args.resume and raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                completed_ids.add(json.loads(line)["run_id"])
    elif not args.finalize_pending_cursor:
        raw_path.write_text("", encoding="utf-8")
        scores_path.write_text("", encoding="utf-8")

    awaiting: list[dict] = []
    completed = 0
    limit = args.max_runs if args.max_runs > 0 else len(pairs)

    for idx, (fixture_id, arm) in enumerate(pairs[:limit], start=1):
        run_id = f"live-{idx:04d}-{fixture_id}-{arm}"
        if run_id in completed_ids:
            print(f"[{idx}/{limit}] SKIP {fixture_id} / {arm} (already recorded)", flush=True)
            completed += 1
            continue
        print(f"[{idx}/{limit}] {fixture_id} / {arm}", flush=True)

        if args.prepare_only:
            prepare(fixture_id, arm, run_id, work_root)
            awaiting.append({"run_id": run_id, "fixture_id": fixture_id, "arm": arm, "run_dir": str(work_root / run_id), "status": "prepared"})
            continue

        if args.finalize_pending_cursor:
            run_dir = work_root / run_id
            if not run_dir.exists() or not (run_dir / "AWAITING_AGENT.json").exists():
                continue
            if not (run_dir / "runner_result.json").exists():
                awaiting.append({"run_id": run_id, "fixture_id": fixture_id, "arm": arm, "run_dir": str(run_dir)})
                continue
            metrics = finalize(fixture_id, arm, run_id, work_root)
            score_run(run_dir)
        else:
            try:
                metrics = run_one(fixture_id, arm, run_id, work_root, args.skip_cursor, args.timeout_sec)
            except Exception as exc:  # noqa: BLE001 - one bad run must not kill the batch
                print(f"  ERROR {run_id}: {exc}", flush=True)
                metrics = {
                    "run_id": run_id,
                    "fixture_id": fixture_id,
                    "arm": arm,
                    "task_class": load_fixture_task_class(fixture_id),
                    "mode": "live",
                    "mechanical_outcome": "blocked_by_runner",
                    "execution_outcome": f"runner_error:{type(exc).__name__}",
                    "input_tokens": None,
                    "output_tokens": None,
                    "cost_usd": None,
                    "wall_minutes": None,
                    "time_to_first_diff_minutes": None,
                    "cold_resume_minutes": None,
                }
                # still produce reviewer scores so downstream counts stay aligned
                try:
                    run_dir = work_root / run_id
                    run_dir.mkdir(parents=True, exist_ok=True)
                    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
                    score_run(run_dir)
                except Exception as score_exc:  # noqa: BLE001
                    print(f"  score-skip {run_id}: {score_exc}", flush=True)
            if metrics is None:
                awaiting.append({"run_id": run_id, "fixture_id": fixture_id, "arm": arm, "run_dir": str(work_root / run_id)})
                continue

        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metrics) + "\n")
        scores_file = work_root / run_id / "reviewer_scores.json"
        if not scores_file.exists():
            print(f"  no reviewer scores for {run_id}; skipping score append", flush=True)
            completed += 1
            continue
        run_scores = json.loads(scores_file.read_text(encoding="utf-8"))
        with scores_path.open("a", encoding="utf-8") as handle:
            for score in run_scores:
                handle.write(json.dumps(score) + "\n")
        completed += 1

    pending_path = results_dir / "awaiting_cursor.json"
    pending_path.write_text(json.dumps(awaiting, indent=2) + "\n", encoding="utf-8")

    summary = {"completed": completed, "awaiting_cursor": len(awaiting), "results_dir": str(results_dir)}
    print(json.dumps(summary, indent=2))

    if completed > 0 and not args.finalize_pending_cursor and not awaiting:
        agg = [
            "python3",
            str(SCRIPTS / "aggregate_results.py"),
            "--results-dir",
            str(results_dir),
            "--label",
            "live-pilot" if args.pilot_only else "live-full",
        ]
        if args.pilot_only:
            agg.append("--pilot-only")
        subprocess.run(agg, cwd=BASE, check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
