#!/usr/bin/env python3
"""Prepare and execute one bake-off arm run."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from arm_profiles import ARMS, TASK_CLASS_BY_FIXTURE, arm_succeeds, failure_mode_for, template_for_fixture  # noqa: E402
from fixture_solver import apply_failure, apply_golden_fix  # noqa: E402

SETUP = SCRIPTS / "setup_fixture.py"
ARM_PROMPTS = BASE / "arm-prompts"


def load_fixture(fixture_id: str) -> dict:
    path = BASE / "fixtures" / f"{fixture_id}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def arm_prompt_path(arm: str) -> Path:
    mapping = {
        "current_vidux": "current-vidux.md",
        "thin_vidux_kernel": "thin-vidux-kernel.md",
        "cursor_native": "cursor-native.md",
        "claude_native": "claude-native.md",
        "codex_native": "codex-native.md",
    }
    name = mapping.get(arm, f"{arm.replace('_', '-')}.md")
    return ARM_PROMPTS / name


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def setup_fixture(fixture_id: str, repo_dir: Path) -> None:
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    result = run_cmd(["python3", str(SETUP), fixture_id, str(repo_dir)], BASE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def capture_artifacts(run_dir: Path, repo_dir: Path) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    script = SCRIPTS / "capture_run_artifacts.sh"
    result = run_cmd(["bash", str(script), str(repo_dir), str(artifacts)], BASE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def run_visible_check(repo_dir: Path) -> tuple[int, str]:
    result = run_cmd(["python3", "checks/visible_check.py"], repo_dir)
    return result.returncode, result.stdout + result.stderr


def run_hidden_oracle(fixture_id: str, repo_dir: Path) -> tuple[str, str]:
    oracle_sh = BASE / "hidden-oracles" / fixture_id / "run.sh"
    if oracle_sh.exists():
        result = run_cmd(["bash", str(oracle_sh), str(repo_dir)], BASE)
        if result.returncode == 0:
            return "pass", result.stdout.strip()
        return "fail", result.stdout + result.stderr
    result = run_cmd(["python3", str(SCRIPTS / "fixture_oracle.py"), fixture_id, str(repo_dir)], BASE)
    if result.returncode == 0:
        return "pass", result.stdout.strip()
    return "fail", result.stdout + result.stderr


def git_first_commit_minutes(repo_dir: Path, prepared_at: float) -> float | None:
    result = run_cmd(["git", "log", "--reverse", "--format=%ct", "-1"], repo_dir)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        ts = int(result.stdout.strip().splitlines()[-1])
    except ValueError:
        return None
    if ts <= int(prepared_at):
        return None
    return round((ts - prepared_at) / 60.0, 2)


def write_live_task(run_dir: Path, fixture: dict, arm: str, prompt_file: Path) -> None:
    arm_text = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""
    task = {
        "fixture_id": fixture["fixture_id"],
        "arm": arm,
        "task_prompt": fixture.get("task_prompt"),
        "visible_acceptance": fixture.get("visible_acceptance", []),
        "allowed_paths": fixture.get("allowed_paths", []),
        "forbidden_paths": fixture.get("forbidden_paths", []),
        "forbidden_actions": fixture.get("forbidden_actions", []),
        "arm_rules": arm_text,
    }
    (run_dir / "LIVE_TASK.json").write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    md = "\n".join(
        [
            "# Live Bake-Off Task",
            "",
            f"**Fixture:** {fixture['fixture_id']}",
            f"**Arm:** {arm}",
            "",
            "## Arm rules",
            arm_text,
            "",
            "## Task",
            fixture.get("task_prompt", ""),
            "",
            "## Visible acceptance",
            *[f"- {item}" for item in fixture.get("visible_acceptance", [])],
            "",
            "## Allowed paths",
            *[f"- `{p}`" for p in fixture.get("allowed_paths", [])],
            "",
            "## Forbidden actions",
            *[f"- {a}" for a in fixture.get("forbidden_actions", [])],
            "",
            "Before stopping, run: `python3 checks/visible_check.py`",
        ]
    )
    (run_dir / "LIVE_TASK.md").write_text(md + "\n", encoding="utf-8")


def prepare_run(args: argparse.Namespace, fixture: dict, run_dir: Path, repo_dir: Path, prompt_file: Path) -> None:
    setup_fixture(args.fixture_id, repo_dir)
    capture_artifacts(run_dir, repo_dir)
    write_live_task(run_dir, fixture, args.arm, prompt_file)
    prepared_at = time.time()
    state = {
        "run_id": run_dir.name,
        "fixture_id": args.fixture_id,
        "arm": args.arm,
        "prepared_at": prepared_at,
        "prepared_at_iso": datetime.fromtimestamp(prepared_at, tz=timezone.utc).isoformat(),
        "status": "prepared",
    }
    (run_dir / "live_state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def finalize_run(args: argparse.Namespace, fixture: dict, run_dir: Path, repo_dir: Path) -> dict:
    state_path = run_dir / "live_state.json"
    if not state_path.exists():
        raise RuntimeError("finalize requires prepare first (missing live_state.json)")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    prepared_at = state.get("prepared_at", time.time())
    finalize_started = time.time()

    visible_rc, visible_out = run_visible_check(repo_dir)
    mechanical, oracle_out = run_hidden_oracle(args.fixture_id, repo_dir)
    if visible_rc != 0:
        mechanical = "fail"

    capture_artifacts(run_dir, repo_dir)
    (run_dir / "artifacts" / "visible-check.txt").write_text(visible_out, encoding="utf-8")
    (run_dir / "artifacts" / "oracle-output.txt").write_text(oracle_out, encoding="utf-8")

    wall_minutes = round((finalize_started - prepared_at) / 60.0, 2)
    first_diff = git_first_commit_minutes(repo_dir, prepared_at)

    runner_meta = {}
    runner_path = run_dir / "runner_result.json"
    if runner_path.exists():
        runner_meta = json.loads(runner_path.read_text(encoding="utf-8"))

    execution = {
        "mode": "live",
        "execution_outcome": runner_meta.get("execution_outcome", "live_agent"),
        "visible_check_rc": visible_rc,
        "visible_check_output": visible_out.strip(),
        "mechanical_outcome": mechanical,
        "oracle_output": oracle_out.strip(),
        "wall_minutes": wall_minutes,
        "time_to_first_diff_minutes": first_diff,
        "plan_tokens": runner_meta.get("input_tokens"),
        "input_tokens": runner_meta.get("input_tokens"),
        "output_tokens": runner_meta.get("output_tokens"),
        "cost_usd": runner_meta.get("cost_usd"),
        "cold_resume_minutes": runner_meta.get("cold_resume_minutes"),
        "runner": runner_meta.get("runner"),
        "runner_log": runner_meta.get("log_path"),
    }

    claim = "pass" if mechanical == "pass" else "fail"
    closeout = "\n".join(
        [
            f"ARM={args.arm}",
            f"fixture_id={args.fixture_id}",
            f"mechanical_claim={claim}",
            f"mode=live",
            f"proof_commands=python3 checks/visible_check.py -> rc {visible_rc}",
            f"real_surface_proof={'artifacts/runtime-proof.html' if (repo_dir / 'artifacts' / 'runtime-proof.html').exists() else 'n/a'}",
            f"known_issues={execution['execution_outcome']}",
        ]
    )
    (run_dir / "closeout.txt").write_text(closeout + "\n", encoding="utf-8")

    state["status"] = "finalized"
    state["finalized_at"] = finalize_started
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    metrics = {
        "run_id": run_dir.name,
        "fixture_id": args.fixture_id,
        "arm": args.arm,
        "task_class": fixture.get("task_class"),
        **execution,
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def execute_simulated(repo_dir: Path, fixture_id: str, arm_id: str, task_class: str) -> dict:
    profile = ARMS[arm_id]
    start = time.time()
    if arm_succeeds(arm_id, fixture_id):
        apply_golden_fix(repo_dir, fixture_id)
        outcome = "success_path"
    else:
        mode = failure_mode_for(arm_id, fixture_id)
        if not mode:
            apply_golden_fix(repo_dir, fixture_id)
            outcome = "success_path"
        else:
            apply_failure(repo_dir, fixture_id, mode)
            outcome = f"failure_path:{mode}"

    visible_rc, visible_out = run_visible_check(repo_dir)
    mechanical, oracle_out = run_hidden_oracle(fixture_id, repo_dir)
    if visible_rc != 0 or mechanical != "pass":
        mechanical = "fail"

    wall_minutes = (time.time() - start) / 60.0
    plan_tokens = profile.plan_tokens_per_task_class.get(task_class, profile.plan_tokens_base)
    cold = profile.cold_resume_minutes if ("cold-resume" in fixture_id or "cold_resume" in task_class) else None

    return {
        "mode": "simulated",
        "execution_outcome": outcome,
        "visible_check_rc": visible_rc,
        "visible_check_output": visible_out.strip(),
        "mechanical_outcome": mechanical,
        "oracle_output": oracle_out.strip(),
        "wall_minutes": round(wall_minutes, 2),
        "time_to_first_diff_minutes": profile.time_to_first_diff_minutes,
        "plan_tokens": plan_tokens,
        "input_tokens": plan_tokens + 1200,
        "output_tokens": 900,
        "cost_usd": round((plan_tokens + 2100) * 0.000003, 4),
        "cold_resume_minutes": cold,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-id", required=True)
    parser.add_argument("--arm", required=True, choices=sorted(ARMS))
    parser.add_argument("--run-id")
    parser.add_argument("--work-root")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--execute", action="store_true", help="simulated only; requires --allow-simulate")
    parser.add_argument("--allow-simulate", action="store_true")
    args = parser.parse_args()

    if args.execute and not args.allow_simulate:
        print("ERROR: --execute requires --allow-simulate (use --prepare + live runner + --finalize)", file=sys.stderr)
        return 2

    fixture = load_fixture(args.fixture_id)
    run_id = args.run_id or f"{args.fixture_id}-{args.arm}-{uuid.uuid4().hex[:8]}"
    work_root = Path(args.work_root or (BASE / "runs")).resolve()
    run_dir = work_root / run_id
    repo_dir = run_dir / "repo"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = arm_prompt_path(args.arm)

    packet = {
        "run_id": run_id,
        "fixture_id": args.fixture_id,
        "arm": args.arm,
        "task_class": fixture.get("task_class"),
        "task_prompt": fixture.get("task_prompt"),
        "arm_prompt_path": str(prompt_file),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "budget": {"pilot_wall_minutes": 90, "max_turns": 40},
    }
    (run_dir / "run_packet.json").write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    if prompt_file.exists():
        shutil.copy2(prompt_file, run_dir / "arm_prompt.md")

    execution: dict = {"mechanical_outcome": "blocked_by_fixture_setup", "mode": "live"}

    if args.prepare:
        prepare_run(args, fixture, run_dir, repo_dir, prompt_file)
        execution = {"mechanical_outcome": "prepared", "mode": "live"}

    if args.finalize:
        execution = finalize_run(args, fixture, run_dir, repo_dir)

    if args.execute and args.allow_simulate:
        if not repo_dir.exists():
            setup_fixture(args.fixture_id, repo_dir)
        task_class = fixture.get("task_class") or TASK_CLASS_BY_FIXTURE.get(
            template_for_fixture(args.fixture_id), "compound"
        )
        execution = execute_simulated(repo_dir, args.fixture_id, args.arm, task_class)
        capture_artifacts(run_dir, repo_dir)
        claim = "pass" if execution["mechanical_outcome"] == "pass" else "fail"
        closeout = "\n".join(
            [
                f"ARM={args.arm}",
                f"fixture_id={args.fixture_id}",
                f"mechanical_claim={claim}",
                f"mode=simulated",
            ]
        )
        (run_dir / "closeout.txt").write_text(closeout + "\n", encoding="utf-8")
        metrics = {"run_id": run_id, "fixture_id": args.fixture_id, "arm": args.arm, **execution}
        (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    if not args.finalize and not args.execute and not args.prepare:
        setup_fixture(args.fixture_id, repo_dir)
        capture_artifacts(run_dir, repo_dir)

    result = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "fixture_id": args.fixture_id,
        "arm": args.arm,
        "prepared": args.prepare,
        "finalized": args.finalize,
        "executed": args.execute,
        "mechanical_outcome": execution.get("mechanical_outcome"),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
