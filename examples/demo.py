#!/usr/bin/env python3
"""Demonstrate a real claim, failed proof, accepted fix, and resumed task."""
from pathlib import Path
import json
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
# Reuse the repository's existing isolated-board environment.
harness = runpy.run_path(str(ROOT / "scripts/shadow-verify-two-seat.py"))
shadow = str(ROOT / "bin/shadow")

with tempfile.TemporaryDirectory(prefix="shadow-demo-", dir="/tmp") as directory:
    scratch = Path(directory)
    scratch_home = scratch / "home"
    portfolio = scratch / "projects"
    sample = portfolio / "hello"
    for folder in (scratch_home, sample, scratch / "bin"):
        folder.mkdir(parents=True, exist_ok=True)
    env = harness["shadow_env"](scratch_home, portfolio, scratch / "bin")

    def run(*args, expected=0):
        result = subprocess.run(args, cwd=sample, env=env, text=True,
                                capture_output=True, timeout=90)
        if expected is not None and result.returncode != expected:
            raise RuntimeError(result.stderr or result.stdout)
        return result

    def git(*args):
        return run("git", "-c", "core.hooksPath=/dev/null", *args)

    print("A local demo. No coding agent or model account required.", flush=True)
    git("init", "-q", "-b", "main")
    git("config", "user.name", "Example Developer")
    git("config", "user.email", "developer@example.invalid")
    (sample / "greet.py").write_text('def greet():\n    return "goodbye"\n')
    (sample / "check.py").write_text('from greet import greet\nassert greet() == "hello", "greet must return hello"\nprint("greeting check passed")\n')
    git("add", "greet.py", "check.py")
    git("commit", "-qm", "Add a failing greeting example")
    created = run(shadow, "init", "--here")
    plan = Path(created.stdout.strip().split(": ", 1)[1])
    plan.write_text('''# Hello

## Brief
- Project: hello
- Mode: ship
- Outcome: greet returns hello, with a check another session can rerun.

## Tasks
### A working greeting
- [pending] greet returns hello ~a1b2 | proof: cmd python3 check.py
- [pending] document the greeting ~b2c3 (DoD) | needs: ~a1b2 | proof: read README.md -> the greeting is explained

## Progress
- LESSON This is a disposable example, not a real project.
''')
    run(shadow, "lint", "--repo", str(sample), str(plan))
    run(shadow, "status", "--by", "first-session")
    board = json.loads((scratch_home / ".shadow/board.json").read_text())
    entity = next(e["id"] for e in board["entities"] if e["project"] == "hello")
    run(shadow, "throw", "--entity", entity, "--task", "~a1b2", "--by", "first-session")
    print("\nClaimed: greet returns hello", flush=True)

    refused = run(shadow, "accept", "--entity", entity, "--repo", str(sample),
                  "--row", "~a1b2", "--by", "first-session", expected=None)
    assert refused.returncode != 0, "Shadow accepted the failing check"
    assert "greet must return hello" in refused.stdout + refused.stderr, refused.stdout + refused.stderr
    assert "[completed] greet returns hello" not in plan.read_text()
    print("Check failed: greet must return hello\nThe task stays open.", flush=True)

    (sample / "greet.py").write_text('def greet():\n    return "hello"\n')
    git("add", "greet.py")
    git("commit", "-qm", "Return the expected greeting")
    accepted = run(shadow, "accept", "--entity", entity, "--repo", str(sample),
                   "--row", "~a1b2", "--by", "first-session")
    assert "[completed] greet returns hello" in plan.read_text()
    print("\nCommitted the fix. Shadow reran the check.\nAccepted: greet returns hello", flush=True)

    resumed = run(shadow, "status", "--by", "next-session")
    assert "document the greeting" in resumed.stdout, resumed.stdout
    board = json.loads((scratch_home / ".shadow/board.json").read_text())
    assert not board["claims"], "Completed work left a claim behind"
    print("\nA fresh session reads the board:", flush=True)
    print(resumed.stdout.strip(), flush=True)
    print("\nDemo passed. The scratch repository and board are removed on exit.", flush=True)
