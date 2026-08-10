#!/usr/bin/env python3
"""Choose and run Shadow's focused checks or deterministic release train."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Iterable, Mapping


ROOT = Path(__file__).resolve().parent.parent
FIRST_WINDOW = "17 6 * * *"
SECOND_WINDOW = "17 18 * * *"
PRESSURE_WINDOW = "47 */3 * * *"
ACCEPTED_CHANGE_COUNT_THRESHOLD = 8
ACCEPTED_CHANGE_AGE_THRESHOLD_HOURS = 24
SEVERITY_THRESHOLD = "high"
RISK_THRESHOLD = "high"
LEVELS = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
SAFE_MODULE = re.compile(r"tests\.test_[a-z0-9_]+(?:\.[A-Za-z0-9_]+)*\Z")

BASELINE = {
    "tests.test_all_boats_law",
    "tests.test_style_guard",
}
BROWSER_BASELINE = {
    "tests.test_browser_shell",
    "tests.test_documented_targets",
    "tests.test_standing_goal",
}

GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("scripts/shadow_root_board.py", "scripts/shadow_board_import.py"), (
        "tests.test_root_board", "tests.test_status_focus", "tests.test_throw",
        "tests.test_return", "tests.test_amp", "tests.test_shadow_accept",
    )),
    (("scripts/shadow-status.py", "scripts/shadow-priority.py"), (
        "tests.test_status_focus", "tests.test_root_board", "tests.test_browser",
    )),
    (("scripts/shadow-amp.py",), ("tests.test_amp", "tests.test_throw", "tests.test_status_focus")),
    (("scripts/shadow-throw.py",), ("tests.test_throw", "tests.test_root_board", "tests.test_gauntlet")),
    (("scripts/shadow-return.py",), ("tests.test_return", "tests.test_root_board", "tests.test_amp")),
    (("scripts/shadow-accept.py",), ("tests.test_shadow_accept", "tests.test_gauntlet", "tests.test_root_board")),
    (("scripts/shadow-lifecycle.py", "schemas/retirement-manifest.v1.json"), (
        "tests.test_lifecycle", "tests.test_root_board", "tests.test_status_focus",
    )),
    (("browser/", "bin/shadow-browse"), (
        "tests.test_browser", "tests.test_browser_shell", "tests.test_status_focus",
        "tests.test_root_board", "tests.test_config_defaults",
    )),
    (("scripts/shadow-lint.py", "scripts/shadow_task_lib.py", "scripts/shadow-init.py"), (
        "tests.test_shadow_lint", "tests.test_shadow_init", "tests.test_grammar_contract",
    )),
    (("install.sh", "scripts/shadow-doctor.py", "scripts/shadow-host-directives.py", "scripts/shadow-verify-host.sh"), (
        "tests.test_install_doctor", "tests.test_host_directives", "tests.test_verify_host",
        "tests.test_standing_goal", "tests.test_release_package",
    )),
    (("scripts/shadow-host.py",), ("tests.test_shadow_host", "tests.test_verify_host")),
    (("scripts/shadow-release-package.py", ".gitattributes", "VERSION", ".claude-plugin/"), (
        "tests.test_release_package", "tests.test_grammar_contract", "tests.test_standing_goal",
    )),
    (("scripts/shadow-buckets.py",), ("tests.test_extension_buckets", "tests.test_amp")),
    (("scripts/shadow-config-cli.py", "scripts/shadow_config.py"), (
        "tests.test_config_defaults", "tests.test_config_parser", "tests.test_extension_buckets",
    )),
    (("scripts/shadow-outcome-validate.py", "browser/outcome_source.py", "browser/decision_mode.py"), (
        "tests.test_outcome_source", "tests.test_outcome_choice", "tests.test_decision_mode",
    )),
    (("scripts/shadow-public-ready-grep-gate.py", "scripts/shadow_scrub_lib.py", "SECURITY.md"), (
        "tests.test_public_ready_grep_gate", "tests.test_secret_scan_workflow",
    )),
    ((".github/", "scripts/shadow-ci.py"), (
        "tests.test_verification_tiers", "tests.test_release_train",
        "tests.test_secret_scan_workflow", "tests.test_browser_shell",
    )),
)

DOC_MODULES = {
    "tests.test_all_boats_law",
    "tests.test_documented_targets",
    "tests.test_grammar_contract",
    "tests.test_public_ready_grep_gate",
    "tests.test_standing_goal",
}
DOC_ROOTS = ("docs/", "README.md", "AGENT.md", "SKILL.md", "skills/", "CONTRIBUTING.md", "PLAN.md")
RELEASE_PATHS = (
    "scripts/shadow-ci.py",
    ".github/workflows/ci.yml",
    "scripts/shadow-release-package.py",
    "schemas/retirement-manifest.v1.json",
    ".gitattributes",
    "CHANGELOG.md",
    "VERSION",
    ".claude-plugin/",
    "install.sh",
)


@dataclass(frozen=True)
class Selection:
    run_all: bool
    modules: tuple[str, ...]
    browser_modules: tuple[str, ...]
    release_contract: bool
    reason: str


def _matches(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def select_paths(paths: Iterable[str]) -> Selection:
    normalized = sorted({
        value[2:] if value.startswith("./") else value
        for path in paths if path
        for value in (str(Path(path).as_posix()),)
    })
    if not normalized:
        return Selection(True, (), tuple(sorted(BROWSER_BASELINE)), True, "no changed paths; full proof")

    modules = set(BASELINE)
    browser = set(BROWSER_BASELINE)
    unknown: list[str] = []
    release_contract = False
    for path in normalized:
        matched = False
        if path.startswith("tests/test_") and path.endswith(".py"):
            modules.add(path[:-3].replace("/", "."))
            matched = True
        if _matches(path, DOC_ROOTS):
            modules.update(DOC_MODULES)
            browser.update(DOC_MODULES)
            matched = True
        for prefixes, selected in GROUPS:
            if _matches(path, prefixes):
                modules.update(selected)
                if _matches(path, ("browser/", ".github/")):
                    browser.update(selected)
                matched = True
        if _matches(path, RELEASE_PATHS):
            release_contract = True
        if path in {"LICENSE", ".gitignore"} or path.startswith("assets/"):
            modules.update(DOC_MODULES)
            browser.update(DOC_MODULES)
            matched = True
        if not matched:
            unknown.append(path)

    if unknown:
        return Selection(
            True,
            (),
            tuple(sorted(browser)),
            True,
            "unmapped paths require full proof: " + ", ".join(unknown),
        )
    if not modules:
        raise ValueError("focused selection is empty")
    return Selection(False, tuple(sorted(modules)), tuple(sorted(browser)), release_contract, "mapped affected proof")


def changed_paths(base: str, head: str) -> list[str]:
    if not base or not head or set(base) == {"0"}:
        raise ValueError("comparison base is missing")
    result = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--name-only", "--no-renames", "-z", base, head, "--"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("comparison base is unavailable")
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def _integer(name: str, value: str, minimum: int, maximum: int) -> int:
    if not re.fullmatch(r"[0-9]+", value or ""):
        raise ValueError(f"{name} must be a decimal integer")
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def pressure_decision(values: Mapping[str, str]) -> tuple[bool, str]:
    accepted = _integer(
        "accepted_change_count", values.get("ACCEPTED_CHANGE_COUNT", ""), 0, 1000
    )
    age = _integer(
        "oldest_accepted_change_hours",
        values.get("OLDEST_ACCEPTED_CHANGE_HOURS", ""),
        0,
        8760,
    )
    severity = values.get("SEVERITY", "none")
    risk = values.get("RELEASE_RISK", "none")
    for name, value in (("severity", severity), ("release_risk", risk)):
        if value not in LEVELS:
            raise ValueError(f"{name} is not a supported level")
    if accepted == 0:
        return False, "no accepted trunk change; no empty release train"
    reasons = []
    if accepted >= ACCEPTED_CHANGE_COUNT_THRESHOLD:
        reasons.append(
            f"accepted change count {accepted}>={ACCEPTED_CHANGE_COUNT_THRESHOLD}"
        )
    if age >= ACCEPTED_CHANGE_AGE_THRESHOLD_HOURS:
        reasons.append(
            f"oldest accepted change age {age}>="
            f"{ACCEPTED_CHANGE_AGE_THRESHOLD_HOURS}h"
        )
    if LEVELS[severity] >= LEVELS[SEVERITY_THRESHOLD]:
        reasons.append(f"severity {severity}>={SEVERITY_THRESHOLD}")
    if LEVELS[risk] >= LEVELS[RISK_THRESHOLD]:
        reasons.append(f"release risk {risk}>={RISK_THRESHOLD}")
    return bool(reasons), "; ".join(reasons) if reasons else "pressure below every versioned threshold"


def repository_pressure(root: Path = ROOT, now: float | None = None) -> dict[str, str]:
    """Accepted-change pressure since the newest reachable release tag."""
    tag = subprocess.run(
        ["git", "-C", str(root), "describe", "--tags", "--match", "v[0-9]*", "--abbrev=0"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    baseline = tag.stdout.strip()
    if tag.returncode or not baseline:
        return {
            "ACCEPTED_CHANGE_COUNT": "0", "OLDEST_ACCEPTED_CHANGE_HOURS": "0",
            "SEVERITY": "none", "RELEASE_RISK": "none",
        }
    log = subprocess.run(
        [
            "git", "-C", str(root), "log", "--no-merges", "--max-count=1001",
            "--format=%ct%x09%s", f"{baseline}..HEAD",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if log.returncode:
        raise ValueError("release-pressure commit history is unreadable")
    commits: list[tuple[int, str]] = []
    for line in log.stdout.splitlines():
        stamp, separator, subject = line.partition("\t")
        if not separator or not stamp.isdigit():
            raise ValueError("release-pressure commit history is malformed")
        commits.append((int(stamp), subject))
    if not commits:
        return {
            "ACCEPTED_CHANGE_COUNT": "0", "OLDEST_ACCEPTED_CHANGE_HOURS": "0",
            "SEVERITY": "none", "RELEASE_RISK": "none",
        }
    changed = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "--no-renames", baseline, "HEAD", "--"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if changed.returncode:
        raise ValueError("release-pressure changed paths are unreadable")
    subjects = "\n".join(subject for _, subject in commits)
    severity = (
        "critical" if re.search(r"(?i)\b(P0|CVE)\b", subjects)
        else "high" if re.search(r"(?i)\b(P1|security)\b", subjects)
        else "none"
    )
    risky = (
        ".github/workflows/", ".claude-plugin/", "SECURITY.md", "VERSION", "install.sh",
        "scripts/shadow-host", "scripts/shadow-release-package.py", "scripts/shadow_root_board.py",
    )
    paths = changed.stdout.splitlines()
    risk = "high" if any(_matches(path, risky) for path in paths) else "none"
    oldest = max(0, int(((now if now is not None else time.time()) - min(ts for ts, _ in commits)) / 3600))
    return {
        "ACCEPTED_CHANGE_COUNT": str(min(len(commits), 1000)),
        "OLDEST_ACCEPTED_CHANGE_HOURS": str(min(oldest, 8760)),
        "SEVERITY": severity,
        "RELEASE_RISK": risk,
    }


def event_plan(
    env: Mapping[str, str],
    pressure_values: Mapping[str, str] | None = None,
) -> dict[str, object]:
    event = env.get("EVENT_NAME", "")
    if event in {"pull_request", "push"}:
        base = env.get("PR_BASE_SHA" if event == "pull_request" else "PUSH_BEFORE_SHA", "")
        try:
            selection = select_paths(changed_paths(base, env.get("HEAD_SHA", "")))
        except ValueError as exc:
            selection = Selection(True, (), tuple(sorted(BROWSER_BASELINE)), True, f"{exc}; full proof")
        return {
            "run_checks": True,
            "run_all": selection.run_all,
            "modules": list(selection.modules),
            "browser_modules": list(selection.browser_modules),
            "release_contract": selection.release_contract,
            "full_gauntlet": selection.release_contract,
            "reason": selection.reason,
        }
    if event == "schedule":
        schedule = env.get("EVENT_SCHEDULE", "")
        if schedule == FIRST_WINDOW:
            run = True
            reason = "nightly release train"
        elif schedule == SECOND_WINDOW:
            twice = env.get("TWICE_DAILY", "0")
            if twice not in {"0", "1"}:
                raise ValueError("TWICE_DAILY must be 0 or 1")
            run = twice == "1"
            reason = "configured second daily release train" if run else "second window disabled"
        elif schedule == PRESSURE_WINDOW:
            run, detail = pressure_decision(pressure_values or repository_pressure())
            reason = f"automatic pressure probe: {detail}"
        else:
            raise ValueError("schedule is not a declared release window")
        return {
            "run_checks": run, "run_all": True, "modules": [],
            "browser_modules": sorted(BROWSER_BASELINE), "release_contract": run,
            "full_gauntlet": run, "reason": reason,
        }
    if event == "workflow_dispatch":
        run, reason = pressure_decision(env)
        return {
            "run_checks": run, "run_all": True, "modules": [],
            "browser_modules": sorted(BROWSER_BASELINE), "release_contract": run,
            "full_gauntlet": run, "reason": reason,
        }
    raise ValueError("event has no declared verification contract")


def _write_outputs(path: Path, plan: Mapping[str, object]) -> None:
    values = {
        "run_checks": str(bool(plan["run_checks"])).lower(),
        "run_all": str(bool(plan["run_all"])).lower(),
        "modules_json": json.dumps(plan["modules"], separators=(",", ":")),
        "browser_modules_json": json.dumps(plan["browser_modules"], separators=(",", ":")),
        "release_contract": str(bool(plan["release_contract"])).lower(),
        "full_gauntlet": str(bool(plan["full_gauntlet"])).lower(),
        "reason": str(plan["reason"]).replace("\n", " "),
    }
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def _run(command: list[str], *, home: Path) -> None:
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    (home / ".config").mkdir(parents=True, exist_ok=True)
    (home / ".cache").mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def run_selected(run_all: bool, modules_json: str) -> None:
    if run_all:
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
    else:
        try:
            modules = json.loads(modules_json)
        except json.JSONDecodeError as exc:
            raise ValueError("modules_json is invalid") from exc
        if not isinstance(modules, list) or not modules or any(
            not isinstance(item, str) or not SAFE_MODULE.fullmatch(item) for item in modules
        ):
            raise ValueError("focused modules must be a non-empty trusted unittest list")
        command = [sys.executable, "-m", "unittest", *modules]
    with tempfile.TemporaryDirectory(prefix="shadow-ci-home-") as tmp:
        _run(command, home=Path(tmp))


def run_gauntlet(scratch_root: Path) -> None:
    scratch_root.mkdir(parents=True, exist_ok=True)
    stages = (
        ("story-e2e-pass-1", [sys.executable, "-m", "unittest", "tests.test_gauntlet"]),
        ("story-e2e-pass-2", [sys.executable, "-m", "unittest", "tests.test_gauntlet"]),
        ("migration-and-lifecycle", [
            sys.executable, "-m", "unittest", "tests.test_root_board", "tests.test_lifecycle",
        ]),
        ("adversarial-and-crash", [
            sys.executable, "-m", "unittest", "tests.test_throw", "tests.test_return",
            "tests.test_shadow_accept",
        ]),
        ("capability-and-rotation", [
            sys.executable, "-m", "unittest", "tests.test_amp", "tests.test_extension_buckets",
            "tests.test_status_focus", "tests.test_browser",
        ]),
        ("rollback-and-upgrade", [
            sys.executable, "-m", "unittest", "tests.test_host_directives",
            "tests.test_install_doctor", "tests.test_verify_host",
        ]),
        ("release-package-and-install", [sys.executable, str(ROOT / "scripts" / "shadow-release-package.py")]),
    )
    for index, (name, command) in enumerate(stages):
        print(f"release stage: {name}", flush=True)
        home = scratch_root / f"home-{index}"
        home.mkdir(parents=True, exist_ok=True)
        _run(command, home=home)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="shadow-ci", description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--github-output", required=True, type=Path)
    run = sub.add_parser("run")
    run.add_argument("--run-all", choices=("true", "false"), default="false")
    run.add_argument("--modules-json", default="[]")
    gauntlet = sub.add_parser("gauntlet")
    gauntlet.add_argument("--scratch-root", required=True, type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "plan":
            plan = event_plan(os.environ)
            _write_outputs(args.github_output, plan)
            print(plan["reason"])
        elif args.command == "run":
            run_selected(args.run_all == "true", args.modules_json)
        else:
            run_gauntlet(args.scratch_root)
    except (OSError, ValueError) as exc:
        print(f"shadow-ci: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
