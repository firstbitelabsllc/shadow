#!/usr/bin/env python3
"""Prove two stable seats coordinate through one disposable Shadow board.

The default is deterministic and invokes no native host. ``--live`` is the
explicit quota-bearing tier. Both modes use only a canonical temporary root,
the real Shadow status/throw/accept verbs, and a closed path-free receipt.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any

from shadow_process_lib import ProcessResult, run_bounded
from shadow_root_board import normalized_origin


ROOT = Path(__file__).resolve().parent.parent
SHADOW = ROOT / "bin" / "shadow"
SCHEMA = "shadow.two-seat-verification.v1"
SEATS = ("claude", "codex")
ROW_BY_PROJECT = {"alpha": "~aa11", "beta": "~bb22"}
DEFAULT_GOAL = """Outcome: prove two seats share one root board.
Authority: the scratch repositories and board created by the sealed harness.
Resume: claim the highest reachable unclaimed checkpoint with your stable seat.
Proof: run the row proof and accept it; do not leave an orphan claim.
"""
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OID_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_GOAL_BYTES = 64 * 1024
CANONICAL_ORIGIN = "github.com/firstbitelabsllc/shadow"


PLAN = """# {name} acceptance fixture

## Brief

- Project: {name}
- Mode: ship
- Priority: {priority}

## Tasks

### Coordinate through one board
- [pending] complete the disposable {name} proof {row} | proof: cmd true

## Progress

- 2026-08-10T00:00:00Z NOTE fixture seeded
"""


class HarnessError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HarnessError("fixture_failed") from exc


def git(cwd: Path, *args: str) -> str:
    result = run(["git", *args], cwd)
    if result.returncode:
        raise HarnessError("fixture_failed")
    return result.stdout.strip()


def source_ref(live: bool) -> str:
    if live:
        configured = git(ROOT, "config", "--get", "remote.origin.url")
        if normalized_origin(configured) != CANONICAL_ORIGIN:
            raise HarnessError("source_origin_mismatch")
        fetched = run(["git", "fetch", "origin", "main", "--quiet"], ROOT)
        if fetched.returncode:
            raise HarnessError("source_fetch_failed")
    result = run(["git", "rev-parse", "origin/main"], ROOT)
    if result.returncode == 0:
        value = result.stdout.strip()
    else:
        try:
            value = (ROOT / "SOURCE_REF").read_text(encoding="ascii").strip()
        except (OSError, UnicodeError) as exc:
            raise HarnessError("source_identity_invalid") from exc
    if not OID_RE.fullmatch(value):
        raise HarnessError("source_identity_invalid")
    if live:
        if git(ROOT, "rev-parse", "HEAD") != value:
            raise HarnessError("source_identity_mismatch")
        if git(ROOT, "status", "--porcelain", "--untracked-files=all"):
            raise HarnessError("source_dirty")
    return value


def goal_bytes(path: Path | None) -> bytes:
    if path is None:
        return DEFAULT_GOAL.encode("utf-8")
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_GOAL_BYTES:
            raise HarnessError("goal_invalid")
        content = path.read_bytes()
        content.decode("utf-8")
    except (OSError, UnicodeError):
        raise HarnessError("goal_invalid")
    if not content.strip():
        raise HarnessError("goal_invalid")
    return content


def mint_repo(scratch: Path, portfolio: Path, name: str, priority: int) -> Path:
    bare = scratch / "forge" / f"{name}.git"
    bare.parent.mkdir(parents=True, exist_ok=True)
    git(scratch, "init", "-q", "--bare", str(bare))
    repo = portfolio / name
    git(scratch, "clone", "-q", str(bare), str(repo))
    git(repo, "config", "user.name", "Shadow Two Seat")
    git(repo, "config", "user.email", "two-seat@example.invalid")
    (repo / "PLAN.md").write_text(
        PLAN.format(name=name, priority=priority, row=ROW_BY_PROJECT[name]),
        encoding="utf-8",
    )
    git(repo, "add", "PLAN.md")
    git(repo, "commit", "-qm", "seed disposable acceptance fixture")
    git(repo, "push", "-q", "origin", "HEAD:main")
    git(repo, "branch", "-q", "--set-upstream-to=origin/main")
    git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
    return repo


def sealed_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in (
        "SHADOW_ROOT",
        "SHADOW_PORTFOLIO_ROOT",
        "SHADOW_DEV_ROOT",
        "SHADOW_PYTHON",
        "SHADOW_PYTHON_COMMAND",
    ):
        env.pop(name, None)
    env["SHADOW_ROOT"] = str(ROOT)
    return env


def shadow_env(home: Path, portfolio: Path, shim: Path) -> dict[str, str]:
    return {
        **sealed_environment(),
        "HOME": str(home),
        "SHADOW_PORTFOLIO_ROOT": str(portfolio),
        "PATH": f"{shim}{os.pathsep}{ROOT / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
    }


def shadow_json(env: dict[str, str], cwd: Path, *args: str) -> dict[str, Any]:
    result = run([str(SHADOW), *args], cwd, env)
    if result.returncode:
        raise HarnessError("board_unavailable")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError("board_unavailable") from exc
    if not isinstance(value, dict):
        raise HarnessError("board_unavailable")
    return value


def next_claim(data: dict[str, Any]) -> tuple[str, str] | None:
    for plan in data.get("v4_plans", []):
        project = plan.get("project")
        row = plan.get("next_unclaimed")
        if project in ROW_BY_PROJECT and row == ROW_BY_PROJECT[project]:
            return project, row
    return None


def deterministic_seat(
    seat: str,
    env: dict[str, str],
    portfolio: Path,
    barrier: threading.Barrier,
) -> tuple[str, str]:
    deadline = time.monotonic() + 20
    claimed: tuple[str, str] | None = None
    while claimed is None and time.monotonic() < deadline:
        candidate = next_claim(shadow_json(env, portfolio, "status", "--json", "--by", seat))
        if candidate is None:
            time.sleep(0.03)
            continue
        project, row = candidate
        result = run(
            [str(SHADOW), "throw", "--repo", str(portfolio / project), "--task", row, "--by", seat],
            portfolio,
            env,
        )
        if result.returncode == 0:
            claimed = candidate
        else:
            time.sleep(0.03)
    if claimed is None:
        raise HarnessError("partial_completion")
    try:
        barrier.wait(timeout=20)
    except threading.BrokenBarrierError as exc:
        raise HarnessError("partial_completion") from exc
    project, row = claimed
    accepted = run(
        [str(SHADOW), "accept", "--repo", str(portfolio / project), "--row", row, "--by", seat],
        portfolio / project,
        env,
    )
    if accepted.returncode:
        raise HarnessError("partial_completion")
    return project, row


def install_scratch_wiring(home: Path, shim_dir: Path, portfolio: Path) -> None:
    goal = run([str(SHADOW), "goal"], ROOT, sealed_environment())
    if goal.returncode:
        raise HarnessError("fixture_failed")
    for mount in (home / ".claude/skills/shadow", home / ".agents/skills/shadow"):
        mount.parent.mkdir(parents=True, exist_ok=True)
        mount.symlink_to(ROOT, target_is_directory=True)
    for directive in (home / ".claude/CLAUDE.md", home / ".codex/AGENTS.md"):
        directive.parent.mkdir(parents=True, exist_ok=True)
        directive.write_text(goal.stdout, encoding="utf-8")
    for bound_seat in SEATS:
        seat_dir = shim_dir / bound_seat
        seat_dir.mkdir(parents=True)
        shim = seat_dir / "shadow"
        shim.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, subprocess, sys\n"
            f"home = pathlib.Path({str(home)!r})\n"
            f"portfolio = pathlib.Path({str(portfolio)!r})\n"
            f"real = {str(SHADOW)!r}\n"
            f"seat = {bound_seat!r}\n"
            "args = sys.argv[1:]\n"
            "if not args or args[0] not in {'status', 'throw', 'accept'}:\n"
            "    raise SystemExit(2)\n"
            "if args.count('--by') != 1:\n"
            "    raise SystemExit(2)\n"
            "try:\n"
            "    if args[args.index('--by') + 1] != seat:\n"
            "        raise SystemExit(2)\n"
            "except IndexError:\n"
            "    raise SystemExit(2)\n"
            "if args[0] == 'status':\n"
            "    if any(value == '--root' or value.startswith('--root=') or value == '--shadowed' or value.startswith('--shadowed=') for value in args):\n"
            "        raise SystemExit(2)\n"
            "elif args.count('--repo') != 1:\n"
            "    raise SystemExit(2)\n"
            "else:\n"
            "    try:\n"
            "        candidate = pathlib.Path(args[args.index('--repo') + 1]).resolve(strict=True)\n"
            "    except (IndexError, OSError):\n"
            "        raise SystemExit(2)\n"
            "    allowed = {(portfolio / 'alpha').resolve(), (portfolio / 'beta').resolve()}\n"
            "    if candidate not in allowed:\n"
            "        raise SystemExit(2)\n"
            "env = dict(os.environ)\n"
            "env['HOME'] = str(home)\n"
            "env['SHADOW_PORTFOLIO_ROOT'] = str(portfolio)\n"
            "result = subprocess.run([real, *args], env=env)\n"
            "try:\n"
            "    board = json.loads((home / '.shadow/board.json').read_text(encoding='utf-8'))\n"
            "    owners = sorted(c.get('owner') for c in board.get('claims', []) if isinstance(c, dict))\n"
            "    event = {'seat': seat, 'session': os.getsid(0), 'verb': args[0], 'returncode': result.returncode, 'owners': owners}\n"
            "    with (home / '.two-seat-command-audit.jsonl').open('a', encoding='utf-8') as stream:\n"
            "        stream.write(json.dumps(event, sort_keys=True) + '\\n')\n"
            "except (OSError, ValueError, json.JSONDecodeError):\n"
            "    raise SystemExit(2)\n"
            "raise SystemExit(result.returncode)\n",
            encoding="utf-8",
        )
        shim.chmod(0o700)


def resolve_host(env_name: str, default: str) -> str:
    candidate = os.environ.get(env_name) or shutil.which(default)
    if not candidate:
        raise HarnessError("host_failed")
    path = Path(candidate)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise HarnessError("host_failed")
    return str(path.resolve())


def host_command(seat: str, binary: str, prompt: str, scratch: Path, final: Path) -> list[str]:
    if seat == "claude":
        return [
            binary,
            "--no-session-persistence",
            "--permission-mode", "acceptEdits",
            "--allowedTools", "Bash(shadow:*)",
            "--add-dir", str(scratch),
            "-p", prompt,
        ]
    return [
        binary,
        "exec", "--ephemeral", "--skip-git-repo-check",
        "--sandbox", "workspace-write", "--add-dir", str(scratch),
        "--output-last-message", str(final), prompt,
    ]


def live_seat(
    seat: str,
    binary: str,
    prompt: str,
    scratch: Path,
    env: dict[str, str],
    timeout: int,
) -> tuple[str, ProcessResult, Path]:
    final = scratch / f"{seat}-final.txt"
    stdout = final if seat == "claude" else scratch / f"{seat}-diagnostics.txt"
    stderr = scratch / f"{seat}-stderr.txt"
    try:
        seat_env = {
            **env,
            "PATH": f"{scratch / 'bin' / seat}{os.pathsep}{env.get('PATH', '')}",
        }
        result = run_bounded(
            host_command(seat, binary, prompt, scratch, final),
            cwd=scratch,
            env=seat_env,
            stdout_path=stdout,
            stderr_path=stderr,
            timeout=timeout,
        )
    except OSError as exc:
        raise HarnessError("host_failed") from exc
    return seat, result, final


def claim_history(home: Path) -> dict[str, str]:
    board_repo = home / ".shadow"
    commits = git(board_repo, "rev-list", "--reverse", "HEAD").splitlines()
    expected_rows = set(ROW_BY_PROJECT.values())
    for commit in commits:
        shown = run(["git", "show", f"{commit}:board.json"], board_repo)
        if shown.returncode:
            raise HarnessError("board_unavailable")
        try:
            payload = json.loads(shown.stdout)
        except json.JSONDecodeError as exc:
            raise HarnessError("board_unavailable") from exc
        claims = payload.get("claims", [])
        mapping = {
            claim.get("row"): claim.get("owner")
            for claim in claims
            if isinstance(claim, dict)
        }
        if set(mapping) == expected_rows and set(mapping.values()) == set(SEATS):
            return mapping
    raise HarnessError("seat_overlap_missing")


def peer_observation(home: Path, sessions: dict[str, int]) -> None:
    try:
        entries = [
            json.loads(line)
            for line in (home / ".two-seat-command-audit.jsonl").read_text(encoding="utf-8").splitlines()
        ]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError("seat_overlap_missing") from exc
    for seat in SEATS:
        own = [
            entry for entry in entries
            if isinstance(entry, dict) and entry.get("seat") == seat
        ]
        if any(entry.get("session") != sessions[seat] for entry in own):
            raise HarnessError("seat_overlap_missing")
        successful = {
            entry.get("verb")
            for entry in own
            if entry.get("session") == sessions[seat] and entry.get("returncode") == 0
        }
        observed_peer = any(
            entry.get("verb") == "status"
            and entry.get("session") == sessions[seat]
            and entry.get("returncode") == 0
            and set(entry.get("owners", [])) == set(SEATS)
            for entry in own
        )
        if successful < {"status", "throw", "accept"} or not observed_peer:
            raise HarnessError("seat_overlap_missing")


def exact_scratch_entities(home: Path, portfolio: Path) -> None:
    try:
        payload = json.loads((home / ".shadow/board.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError("board_unavailable") from exc
    observed = {
        (entity.get("project"), Path(entity.get("plan", "")).resolve())
        for entity in payload.get("entities", [])
        if isinstance(entity, dict)
    }
    expected = {
        (project, (portfolio / project / "PLAN.md").resolve())
        for project in ROW_BY_PROJECT
    }
    if observed != expected:
        raise HarnessError("board_drift")


def final_facts(home: Path, portfolio: Path, env: dict[str, str], initial: int) -> tuple[dict[str, Any], dict[str, bool]]:
    data = shadow_json(env, portfolio, "status", "--json", "--by", "observer")
    board = data.get("root_board", {})
    final_revision = board.get("revision")
    if not isinstance(final_revision, int):
        raise HarnessError("board_unavailable")
    in_flight = shadow_json(env, portfolio, "status", "--in-flight", "--json")
    claims = len(in_flight.get("rows", []))
    exact_scratch_entities(home, portfolio)
    completed_rows: dict[str, bool] = {}
    for project, row in ROW_BY_PROJECT.items():
        text = (portfolio / project / "PLAN.md").read_text(encoding="utf-8")
        completed_rows[row] = (
            f"- [completed] complete the disposable {project} proof {row}" in text
            and f"{row} PROOF" in text
        )
    priorities = {
        project.get("project"): project.get("priority")
        for project in board.get("projects", [])
        if isinstance(project, dict)
    }
    if priorities.get("alpha") != 1 or priorities.get("beta") != 2:
        raise HarnessError("board_drift")
    facts = {
        "initial_revision": initial,
        "final_revision": final_revision,
        "completed": sum(completed_rows.values()),
        "claims": claims,
    }
    owners = claim_history(home)
    completed_seats = {
        owner: completed_rows.get(row, False)
        for row, owner in owners.items()
    }
    return facts, completed_seats


def receipt(mode: str, goal_hash: str, ref: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "inconclusive",
        "mode": mode,
        "goal_sha256": goal_hash,
        "origin_main": ref,
        "seats": [{"name": seat, "completed": False} for seat in SEATS],
        "board": {"initial_revision": 0, "final_revision": 0, "completed": 0, "claims": 0},
        "failure": "fixture_failed",
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--live", action="store_true", help="invoke one real Claude and Codex session")
    value.add_argument("--goal-file", type=Path, help="frozen seat-neutral goal (required with --live)")
    value.add_argument("--timeout-seconds", type=int, default=120)
    value.add_argument("--json", action="store_true", help="emit the closed machine receipt")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.live and args.goal_file is None:
        parser().error("--live requires --goal-file")
    if args.timeout_seconds < 1:
        parser().error("--timeout-seconds must be positive")
    mode = "live" if args.live else "offline"
    goal_hash = "0" * 64
    ref = "0" * 40
    public = receipt(mode, goal_hash, ref)
    code = 1
    try:
        goal = goal_bytes(args.goal_file)
        goal_hash = hashlib.sha256(goal).hexdigest()
        public["goal_sha256"] = goal_hash
        ref = source_ref(args.live)
        public["origin_main"] = ref
        operator_home = Path(os.environ.get("HOME", "")).resolve()
        with tempfile.TemporaryDirectory(prefix="shadow-two-seat-") as dirname:
            scratch = Path(dirname).resolve(strict=True)
            if scratch == operator_home or scratch.is_relative_to(operator_home) or operator_home.is_relative_to(scratch):
                raise HarnessError("unsafe_scratch")
            if scratch == ROOT or scratch.is_relative_to(ROOT) or ROOT.is_relative_to(scratch):
                raise HarnessError("unsafe_scratch")
            home = scratch / "home"
            portfolio = scratch / "portfolio"
            shim = scratch / "bin"
            home.mkdir()
            portfolio.mkdir()
            install_scratch_wiring(home, shim, portfolio)
            mint_repo(scratch, portfolio, "alpha", 1)
            mint_repo(scratch, portfolio, "beta", 2)
            env = shadow_env(home, portfolio, shim)
            initial_data = shadow_json(env, scratch, "status", "--json", "--by", "observer")
            initial = initial_data["root_board"]["revision"]
            if args.live:
                text = goal.decode("utf-8")
                base = (
                    f"{text}\n\nShared identity: goal SHA-256 {goal_hash}; "
                    f"origin/main {ref}. Use stable seat {{seat}}. "
                    "Operate through the Shadow standing goal, complete one reachable "
                    "checkpoint with proof, then print the shared goal SHA-256 and ref."
                )
                binaries = {
                    "claude": resolve_host("SHADOW_CLAUDE_CODE_BIN", "claude"),
                    "codex": resolve_host("SHADOW_CODEX_BIN", "codex"),
                }
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [
                        pool.submit(live_seat, seat, binaries[seat], base.format(seat=seat), scratch, env, args.timeout_seconds)
                        for seat in SEATS
                    ]
                    host_results = [future.result() for future in futures]
                if any(result.returncode != 0 for _, result, _ in host_results):
                    if any(result.returncode != 124 for _, result, _ in host_results):
                        raise HarnessError("host_failed")
                    raise HarnessError("host_timeout")
                if any(result.timed_out for _, result, _ in host_results):
                    raise HarnessError("host_timeout")
                for _, _, final in host_results:
                    try:
                        answer = final.read_text(encoding="utf-8")
                    except (OSError, UnicodeError):
                        raise HarnessError("identity_mismatch")
                    if goal_hash not in answer or ref not in answer:
                        raise HarnessError("identity_mismatch")
            else:
                barrier = threading.Barrier(2)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(deterministic_seat, seat, env, portfolio, barrier) for seat in SEATS]
                    for future in futures:
                        future.result()
            facts, completed = final_facts(home, portfolio, env, initial)
            public["board"] = facts
            public["seats"] = [
                {"name": seat, "completed": completed.get(seat, False)}
                for seat in SEATS
            ]
            if facts["completed"] != 2 or facts["claims"] != 0:
                raise HarnessError("partial_completion")
            if args.live:
                peer_observation(
                    home,
                    {seat: result.session_id for seat, result, _ in host_results},
                )
            public["status"] = "pass"
            public["failure"] = None
            code = 0
    except HarnessError as exc:
        public["failure"] = exc.code
        # Preserve whatever final board state was safely observed above.
        if exc.code == "board_drift":
            public["failure"] = "board_drift"
    except Exception:
        # Public output is a closed receipt even when an unexpected local
        # launch or filesystem failure occurs. Diagnostics remain inside the
        # disposable root and are removed; private paths never reach stdout.
        public["failure"] = "internal_error"
    if args.json:
        print(json.dumps(public, sort_keys=True))
    elif code == 0:
        print(f"two-seat verification passed ({mode}); 2 completed, 0 claims")
    else:
        print(f"two-seat verification inconclusive: {public['failure']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
