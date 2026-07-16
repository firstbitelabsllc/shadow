#!/usr/bin/env python3
"""Invoke live agent runners for bake-off arms."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"

CLAUDE_BIN = os.environ.get("BAKEOFF_CLAUDE_BIN", shutil.which("claude") or "/Users/leokwan/.local/bin/claude")
CODEX_BIN = os.environ.get("BAKEOFF_CODEX_BIN", shutil.which("codex") or "/opt/homebrew/bin/codex")

CURSOR_ARMS = {"cursor_native"}  # driven by the real Cursor agent in-session
CLAUDE_ARMS = {"claude_native", "current_vidux", "thin_vidux_kernel"}
CODEX_ARMS = {"codex_native"}


def read_task(run_dir: Path) -> str:
    md = run_dir / "LIVE_TASK.md"
    if md.exists():
        return md.read_text(encoding="utf-8")
    data = json.loads((run_dir / "LIVE_TASK.json").read_text(encoding="utf-8"))
    return json.dumps(data, indent=2)


def parse_usage(text: str) -> dict:
    """Best-effort token extraction from CLI output."""
    input_tokens = None
    output_tokens = None
    for pattern in [
        r"input[_ ]tokens?[:\s]+(\d+)",
        r"output[_ ]tokens?[:\s]+(\d+)",
        r'"input_tokens"\s*:\s*(\d+)',
        r'"output_tokens"\s*:\s*(\d+)',
    ]:
        pass
    m_in = re.search(r"(?:input[_ ]tokens?|prompt_tokens)[:\s\"]+(\d+)", text, re.I)
    m_out = re.search(r"(?:output[_ ]tokens?|completion_tokens)[:\s\"]+(\d+)", text, re.I)
    if m_in:
        input_tokens = int(m_in.group(1))
    if m_out:
        output_tokens = int(m_out.group(1))
    cost_usd = None
    m_cost = re.search(r"\$([0-9.]+)", text)
    if m_cost:
        cost_usd = float(m_cost.group(1))
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd}


def parse_claude_json(output: str) -> dict:
    """Parse claude --output-format json envelope for usage/cost.

    Claude may emit a single result object or a JSON array of streamed events;
    the terminal ``type == "result"`` element carries total_cost_usd + usage.
    """
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return parse_usage(output)

    result_obj = None
    if isinstance(data, list):
        for item in reversed(data):
            if isinstance(item, dict) and (item.get("type") == "result" or "total_cost_usd" in item):
                result_obj = item
                break
        if result_obj is None and data and isinstance(data[-1], dict):
            result_obj = data[-1]
    elif isinstance(data, dict):
        result_obj = data

    if not isinstance(result_obj, dict):
        return parse_usage(output)

    usage = result_obj.get("usage") or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    cost = result_obj.get("total_cost_usd") or result_obj.get("cost_usd")
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost}


def run_claude(run_dir: Path, repo_dir: Path, arm: str, timeout_sec: int) -> dict:
    prompt = read_task(run_dir)
    log_path = run_dir / "runner_claude.log"
    cmd = [
        CLAUDE_BIN,
        "--print",
        "--output-format",
        "json",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Edit",
        "Write",
        "Read",
        "Bash",
        "-p",
        prompt,
    ]
    started = time.time()
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SIMPLE"}
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_sec,
            env=env,
        )
        output = result.stdout
        rc = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\nTIMEOUT"
        rc = 124
    log_path.write_text(output, encoding="utf-8")
    usage = parse_claude_json(output)
    return {
        "runner": "claude_cli",
        "arm": arm,
        "exit_code": rc,
        "wall_seconds": round(time.time() - started, 2),
        "log_path": str(log_path),
        "execution_outcome": "live_claude" if rc == 0 else f"claude_exit_{rc}",
        **usage,
    }


def run_codex(run_dir: Path, repo_dir: Path, arm: str, timeout_sec: int) -> dict:
    prompt = read_task(run_dir)
    log_path = run_dir / "runner_codex.log"
    last_msg = run_dir / "codex_last.txt"
    cmd = [
        CODEX_BIN,
        "exec",
        "-C",
        str(repo_dir),
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "-o",
        str(last_msg),
        "-",
    ]
    started = time.time()
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_sec,
        )
        output = result.stdout
        rc = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\nTIMEOUT"
        rc = 124
    log_path.write_text(output, encoding="utf-8")
    usage = parse_usage(output)
    return {
        "runner": "codex_cli",
        "arm": arm,
        "exit_code": rc,
        "wall_seconds": round(time.time() - started, 2),
        "log_path": str(log_path),
        "execution_outcome": "live_codex" if rc == 0 else f"codex_exit_{rc}",
        **usage,
    }


def mark_cursor_awaiting(run_dir: Path, arm: str) -> dict:
    payload = {
        "runner": "cursor_in_session",
        "arm": arm,
        "status": "AWAITING_AGENT",
        "message": "Cursor agent must edit repo_dir then mark runner_result.json complete",
        "repo_dir": str(run_dir / "repo"),
    }
    (run_dir / "AWAITING_AGENT.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def mark_cursor_complete(run_dir: Path, arm: str, notes: str = "cursor_agent_complete") -> dict:
    payload = {
        "runner": "cursor_in_session",
        "arm": arm,
        "status": "complete",
        "execution_outcome": notes,
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
    }
    (run_dir / "runner_result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    awaiting = run_dir / "AWAITING_AGENT.json"
    if awaiting.exists():
        awaiting.unlink()
    return payload


def invoke(run_dir: Path, arm: str, timeout_sec: int = 5400, skip_cursor: bool = False) -> dict:
    run_dir = run_dir.resolve()
    repo_dir = run_dir / "repo"
    if not repo_dir.exists():
        raise FileNotFoundError(f"missing repo: {repo_dir}")

    if arm in CURSOR_ARMS:
        if skip_cursor:
            return mark_cursor_awaiting(run_dir, arm)
        if (run_dir / "runner_result.json").exists():
            return json.loads((run_dir / "runner_result.json").read_text(encoding="utf-8"))
        return mark_cursor_awaiting(run_dir, arm)

    if arm in CLAUDE_ARMS:
        result = run_claude(run_dir, repo_dir, arm, timeout_sec)
    elif arm in CODEX_ARMS:
        result = run_codex(run_dir, repo_dir, arm, timeout_sec)
    else:
        raise ValueError(f"unknown arm: {arm}")

    (run_dir / "runner_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--arm", required=True)
    parser.add_argument("--timeout-sec", type=int, default=5400)
    parser.add_argument("--skip-cursor", action="store_true")
    parser.add_argument("--mark-cursor-complete", action="store_true")
    parser.add_argument("--notes", default="cursor_agent_complete")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if args.mark_cursor_complete:
        result = mark_cursor_complete(run_dir, args.arm, args.notes)
    else:
        result = invoke(run_dir, args.arm, args.timeout_sec, skip_cursor=args.skip_cursor)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
