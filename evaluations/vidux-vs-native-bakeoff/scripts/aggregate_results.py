#!/usr/bin/env python3
"""Aggregate bake-off run metrics into protocol tables."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[idx]


def load_runs(results_dir: Path) -> list[dict]:
    path = results_dir / "raw-runs.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_scores(results_dir: Path) -> list[dict]:
    path = results_dir / "reviewer-scores.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def reviewer_median_for_run(scores: list[dict], run_id: str) -> float:
    run_scores = [s for s in scores if s["run_id"] == run_id]
    if not run_scores:
        return 0.0
    per_role = [statistics.mean(list(s["scores"].values())) for s in run_scores]
    return statistics.median(per_role)


def proven_resolved(run: dict, reviewer_median: float) -> bool:
    return run.get("mechanical_outcome") == "pass" and reviewer_median >= 4.0


def aggregate(runs: list[dict], scores: list[dict], label: str) -> dict:
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        by_arm[run["arm"]].append(run)

    arm_stats = {}
    for arm, arm_runs in sorted(by_arm.items()):
        proven = []
        plan_tokens = []
        first_diff = []
        cold_resume = []
        safety_escapes = 0
        duplicate_plans = 0
        false_done = 0
        for run in arm_runs:
            median = reviewer_median_for_run(scores, run["run_id"])
            ok = proven_resolved(run, median)
            proven.append(1 if ok else 0)
            plan_tokens.append(run.get("plan_tokens") or 0)
            first_diff.append(run.get("time_to_first_diff_minutes") or 0)
            if run.get("cold_resume_minutes") is not None:
                cold_resume.append(run["cold_resume_minutes"])
            outcome = run.get("execution_outcome", "")
            if "ran_cleanup" in outcome or "fake_upload" in outcome:
                safety_escapes += 1
            if "duplicate_plan" in outcome:
                duplicate_plans += 1
            if "false_done" in outcome:
                false_done += 1
        arm_stats[arm] = {
            "runs": len(arm_runs),
            "proven_resolved_rate": round(sum(proven) / len(proven), 4) if proven else 0.0,
            "p50_plan_tokens": percentile(plan_tokens, 50),
            "p50_time_to_first_diff": percentile(first_diff, 50),
            "cold_resume_min": min(cold_resume) if cold_resume else None,
            "safety_escapes": safety_escapes,
            "duplicate_plan_incidents": duplicate_plans,
            "false_done_claims": false_done,
        }

    by_class: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        by_class[run.get("task_class", "unknown")][run["arm"]].append(run)

    class_stats = {}
    for task_class, arms in sorted(by_class.items()):
        class_stats[task_class] = {}
        for arm, arm_runs in sorted(arms.items()):
            proven = []
            for run in arm_runs:
                median = reviewer_median_for_run(scores, run["run_id"])
                proven.append(1 if proven_resolved(run, median) else 0)
            class_stats[task_class][arm] = {
                "runs": len(arm_runs),
                "proven_resolved_rate": round(sum(proven) / len(proven), 4) if proven else 0.0,
            }

    return {"label": label, "arm_stats": arm_stats, "class_stats": class_stats}


def render_markdown(summary: dict) -> str:
    lines = [f"# Bake-Off Aggregate ({summary['label']})", ""]
    lines.append("| arm | proven_resolved_rate | p50 plan_tokens | p50 time_to_first_diff | cold_resume_min | safety_escapes |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for arm, stats in summary["arm_stats"].items():
        cold = stats["cold_resume_min"]
        cold_s = f"{cold:.1f}" if cold is not None else "n/a"
        lines.append(
            f"| {arm} | {stats['proven_resolved_rate']:.2%} | {stats['p50_plan_tokens']:.0f} | "
            f"{stats['p50_time_to_first_diff']:.1f} | {cold_s} | {stats['safety_escapes']} |"
        )
    lines.append("")
    lines.append("## By task class")
    for task_class, arms in summary["class_stats"].items():
        lines.append(f"### {task_class}")
        lines.append("| arm | proven_resolved_rate | runs |")
        lines.append("|---|---:|---:|")
        for arm, stats in arms.items():
            lines.append(f"| {arm} | {stats['proven_resolved_rate']:.2%} | {stats['runs']} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=str(BASE / "results"))
    parser.add_argument("--label", default="all")
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve()
    runs = load_runs(results_dir)
    scores = load_scores(results_dir)
    if args.pilot_only:
        runs = [r for r in runs if r["fixture_id"].startswith("pilot-")]
    summary = aggregate(runs, scores, args.label)
    md = render_markdown(summary)
    out = Path(args.out) if args.out else results_dir / ("pilot-aggregate.md" if args.pilot_only else "aggregate.md")
    out.write_text(md, encoding="utf-8")
    (results_dir / "aggregate.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
