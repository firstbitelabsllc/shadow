#!/usr/bin/env python3
"""Run bake-off matrix: setup, execute, score, aggregate."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"


def discover_fixtures(pilot_only: bool) -> list[str]:
    fixtures = sorted(p.stem for p in (BASE / "fixtures").glob("*.json") if p.stem != "template-fixture")
    if pilot_only:
        fixtures = [f for f in fixtures if f.startswith("pilot-")]
    else:
        manifest = BASE / "fixtures" / "full-manifest.json"
        if manifest.exists():
            fixtures = json.loads(manifest.read_text(encoding="utf-8"))
    return fixtures


def load_fixture_task_class(fixture_id: str) -> str:
    data = json.loads((BASE / "fixtures" / f"{fixture_id}.json").read_text(encoding="utf-8"))
    return data.get("task_class", "compound")


def template_for(fixture_id: str) -> str:
    from setup_fixture import template_for as tf

    return tf(fixture_id)


def arm_succeeds_extended(arm_id: str, fixture_id: str) -> bool:
    sys.path.insert(0, str(SCRIPTS))
    from arm_profiles import ARMS, arm_succeeds

    if arm_succeeds(arm_id, fixture_id):
        return True
    template = template_for(fixture_id)
    if template != fixture_id and arm_succeeds(arm_id, template):
        return True
    profile = ARMS[arm_id]
    if fixture_id in profile.failure_mode:
        return False
    if template in profile.succeeds_on:
        return True
    if template in profile.failure_mode:
        return False
    return arm_id in {"current_vidux"}


def run_one(fixture_id: str, arm: str, run_id: str, work_root: Path) -> dict:
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
        "--execute",
    ]
    result = subprocess.run(cmd, cwd=BASE, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr)
    payload = json.loads(result.stdout)
    run_dir = Path(payload["run_dir"])
    score_cmd = ["python3", str(SCRIPTS / "build_reviewer_packet.py"), str(run_dir)]
    subprocess.run(score_cmd, cwd=BASE, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["task_class"] = load_fixture_task_class(fixture_id)
    metrics["template_fixture_id"] = template_for(fixture_id)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--results-dir", default=str(BASE / "results"))
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    work_root = BASE / "runs"
    work_root.mkdir(parents=True, exist_ok=True)

    fixtures = discover_fixtures(args.pilot_only)
    arms = ["cursor_native", "claude_native", "codex_native", "current_vidux", "thin_vidux_kernel"]
    pairs = [(f, a) for f in fixtures for a in arms]
    rng = random.Random(args.seed)
    rng.shuffle(pairs)
    (results_dir / "randomization.json").write_text(
        json.dumps({"seed": args.seed, "order": [{"fixture_id": f, "arm": a} for f, a in pairs]}, indent=2) + "\n",
        encoding="utf-8",
    )

    raw_path = results_dir / "raw-runs.jsonl"
    scores_path = results_dir / "reviewer-scores.jsonl"
    if raw_path.exists():
        raw_path.unlink()
    if scores_path.exists():
        scores_path.unlink()

    for idx, (fixture_id, arm) in enumerate(pairs, start=1):
        run_id = f"run-{idx:04d}-{fixture_id}-{arm}"
        print(f"[{idx}/{len(pairs)}] {fixture_id} / {arm}", flush=True)
        metrics = run_one(fixture_id, arm, run_id, work_root)
        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metrics) + "\n")
        run_scores = json.loads((work_root / run_id / "reviewer_scores.json").read_text(encoding="utf-8"))
        with scores_path.open("a", encoding="utf-8") as handle:
            for score in run_scores:
                handle.write(json.dumps(score) + "\n")

    agg_cmd = [
        "python3",
        str(SCRIPTS / "aggregate_results.py"),
        "--results-dir",
        str(results_dir),
        "--label",
        "pilot" if args.pilot_only else "full",
    ]
    if args.pilot_only:
        agg_cmd.append("--pilot-only")
    subprocess.run(agg_cmd, cwd=BASE, check=True)
    if not args.pilot_only:
        subprocess.run(
            ["python3", str(SCRIPTS / "apply_decision_thresholds.py"), "--results-dir", str(results_dir)],
            cwd=BASE,
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
