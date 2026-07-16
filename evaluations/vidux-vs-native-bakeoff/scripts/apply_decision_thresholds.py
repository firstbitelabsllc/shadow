#!/usr/bin/env python3
"""Apply pre-registered keep/kernelize/cut thresholds from PROTOCOL.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
NATIVE_ARMS = ["cursor_native", "claude_native", "codex_native"]


def best_native(arm_stats: dict, key: str, higher_better: bool = True) -> tuple[str, float]:
    values = {arm: arm_stats[arm][key] for arm in NATIVE_ARMS if arm in arm_stats and arm_stats[arm].get(key) is not None}
    if not values:
        return "cursor_native", 0.0
    if higher_better:
        arm = max(values, key=values.get)
    else:
        arm = min(values, key=values.get)
    return arm, values[arm]


def route_task_class(class_stats: dict, task_class: str, arm_stats: dict) -> str:
    arms = class_stats.get(task_class, {})
    if not arms:
        return "cursor_native"
    best = max(arms.items(), key=lambda item: item[1]["proven_resolved_rate"])
    best_arm, best_rate = best
    native_rates = [arms[a]["proven_resolved_rate"] for a in NATIVE_ARMS if a in arms]
    best_native_rate = max(native_rates) if native_rates else 0.0
    thin_rate = arms.get("thin_vidux_kernel", {}).get("proven_resolved_rate", 0.0)
    full_rate = arms.get("current_vidux", {}).get("proven_resolved_rate", 0.0)

    if task_class == "atomic":
        return "cursor_native"
    if task_class in {"cold_resume", "convergence", "safety"}:
        if full_rate >= best_native_rate:
            return "current_vidux"
        if thin_rate >= best_native_rate:
            return "thin_vidux_kernel"
        return best_arm
    if task_class in {"plan_noise", "compound"}:
        if thin_rate >= full_rate and thin_rate >= best_native_rate:
            return "thin_vidux_kernel"
        if full_rate > best_native_rate:
            return "current_vidux"
        return best_arm if best_rate >= thin_rate else "thin_vidux_kernel"
    if best_native_rate >= full_rate and best_native_rate >= thin_rate:
        return best_arm if best_arm in NATIVE_ARMS else "cursor_native"
    if thin_rate >= full_rate:
        return "thin_vidux_kernel"
    return "current_vidux"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=str(BASE / "results"))
    args = parser.parse_args()
    results_dir = Path(args.results_dir).resolve()
    summary = json.loads((results_dir / "aggregate.json").read_text(encoding="utf-8"))
    arm_stats = summary["arm_stats"]
    class_stats = summary["class_stats"]

    best_native_arm, best_native_rate = best_native(arm_stats, "proven_resolved_rate", True)
    full_rate = arm_stats.get("current_vidux", {}).get("proven_resolved_rate", 0.0)
    thin_rate = arm_stats.get("thin_vidux_kernel", {}).get("proven_resolved_rate", 0.0)
    _, best_native_cold = best_native(arm_stats, "cold_resume_min", False)
    full_cold = arm_stats.get("current_vidux", {}).get("cold_resume_min")
    thin_cold = arm_stats.get("thin_vidux_kernel", {}).get("cold_resume_min")

    keep_current = (
        full_rate >= best_native_rate + 0.05 or (abs(full_rate - best_native_rate) <= 0.02 and full_cold and full_cold < best_native_cold)
    ) and arm_stats.get("current_vidux", {}).get("safety_escapes", 1) == 0

    kernelize = (
        thin_rate >= full_rate and arm_stats.get("thin_vidux_kernel", {}).get("p50_plan_tokens", 99999)
        <= arm_stats.get("current_vidux", {}).get("p50_plan_tokens", 0) * 0.85
    ) or (
        full_cold and thin_cold and full_rate > thin_rate and arm_stats.get("current_vidux", {}).get("p50_time_to_first_diff", 0)
        > arm_stats.get("thin_vidux_kernel", {}).get("p50_time_to_first_diff", 0) * 1.15
    )

    routing = {task_class: route_task_class(class_stats, task_class, arm_stats) for task_class in sorted(class_stats)}

    lines = [
        "# Bake-Off Decision",
        "",
        f"Best native arm overall: **{best_native_arm}** ({best_native_rate:.2%} proven_resolved_rate)",
        "",
        "## Threshold outcomes",
        f"- Keep current Vidux for mammoth/multi-session: **{'YES' if keep_current else 'NO'}**",
        f"- Kernelize Vidux: **{'YES' if kernelize else 'NO'}**",
        "",
        "## Task-class routing",
        "```text",
    ]
    for task_class, arm in routing.items():
        lines.append(f"{task_class:16} → {arm}")
    lines.extend(["```", ""])
    decision = {
        "keep_current_vidux": keep_current,
        "kernelize_vidux": kernelize,
        "best_native_arm": best_native_arm,
        "routing": routing,
    }
    (results_dir / "decision.json").write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    (results_dir / "decision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
