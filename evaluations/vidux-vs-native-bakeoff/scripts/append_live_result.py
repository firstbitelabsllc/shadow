#!/usr/bin/env python3
"""Append finalized live run metrics to results/live raw jsonl files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--results-dir", default=str(BASE / "results" / "live"))
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    results_dir = Path(args.results_dir).resolve()
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    scores = json.loads((run_dir / "reviewer_scores.json").read_text(encoding="utf-8"))

    raw_path = results_dir / "raw-runs.jsonl"
    scores_path = results_dir / "reviewer-scores.jsonl"
    results_dir.mkdir(parents=True, exist_ok=True)

    existing = {json.loads(line)["run_id"] for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()} if raw_path.exists() else set()
    if metrics["run_id"] not in existing:
        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metrics) + "\n")
    with scores_path.open("a", encoding="utf-8") as handle:
        for score in scores:
            handle.write(json.dumps(score) + "\n")

    print(json.dumps({"appended": metrics["run_id"], "mechanical_outcome": metrics["mechanical_outcome"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
