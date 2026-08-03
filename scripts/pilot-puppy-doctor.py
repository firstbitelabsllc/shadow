#!/usr/bin/env python3
"""Read-only Pilot Puppy installation doctor."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(os.environ.get("PILOT_PUPPY_ROOT", Path(__file__).resolve().parent.parent)).resolve()
HOSTS = ("codex", "claude-code", "cursor")
MOUNTS = (
    Path.home() / ".claude" / "skills" / "pilot-puppy",
    Path.home() / ".agents" / "skills" / "pilot-puppy",
    Path.home() / ".cursor" / "skills" / "pilot-puppy",
)


def check(name: str, state: str, detail: str, **data: Any) -> dict[str, Any]:
    return {"name": name, "state": state, "detail": detail, **data}


def identity_check() -> dict[str, Any]:
    try:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        version = (ROOT / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, IndexError) as exc:
        return check("product identity", "fail", f"metadata is unreadable: {exc}")
    valid = (
        package.get("name") == "pilot-puppy"
        and package.get("version") == version
        and plugin.get("name") == "pilot-puppy"
        and plugin.get("version") == version
        and (ROOT / "SKILL.md").is_file()
        and (ROOT / "bin" / "pilot-puppy").is_file()
    )
    return check(
        "product identity",
        "pass" if valid else "fail",
        f"pilot-puppy {version}" if valid else "package, plugin, skill, command, and version disagree",
        version=version,
    )


def tool_check(name: str, executable: str, *, required: bool) -> dict[str, Any]:
    path = shutil.which(executable)
    if path:
        return check(name, "pass", str(Path(path).resolve()), executable=executable)
    return check(name, "fail" if required else "warn", f"{executable} is not on PATH", executable=executable)


def cli_check() -> dict[str, Any]:
    path = shutil.which("pilot-puppy")
    if not path:
        return check("PATH command", "warn", "pilot-puppy is not installed on PATH")
    expected = Path(os.environ.get("PILOT_PUPPY_DOCTOR_EXPECTED_CLI", ROOT / "bin" / "pilot-puppy")).resolve()
    actual = Path(path).resolve()
    if actual != expected:
        return check("PATH command", "fail", f"resolves to {actual}, expected {expected}")
    return check("PATH command", "pass", str(actual))


def host_checks() -> list[dict[str, Any]]:
    script = ROOT / "scripts" / "pilot-puppy-host.py"
    results = []
    available = 0
    for host in HOSTS:
        result = subprocess.run(
            [sys.executable, str(script), "probe", "--host", host, "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            available += 1
            try:
                payload = json.loads(result.stdout)
                detail = payload.get("version") or payload.get("command") or "available"
            except json.JSONDecodeError:
                detail = "available"
            results.append(check(f"native host: {host}", "pass", str(detail)))
        else:
            results.append(check(f"native host: {host}", "warn", "not available"))
    results.append(
        check(
            "native host floor",
            "pass" if available else "fail",
            f"{available} of {len(HOSTS)} hosts available",
            available=available,
        )
    )
    return results


def mount_checks() -> list[dict[str, Any]]:
    expected = (ROOT / "SKILL.md").resolve()
    results = []
    for mount in MOUNTS:
        skill = mount / "SKILL.md"
        if not skill.exists():
            results.append(check(f"skill mount: {mount.parent.parent.name}", "warn", f"missing {mount}"))
            continue
        actual = skill.resolve()
        state = "pass" if actual == expected else "fail"
        detail = str(actual) if state == "pass" else f"resolves to {actual}, expected {expected}"
        results.append(check(f"skill mount: {mount.parent.parent.name}", state, detail))
    return results


def collect() -> dict[str, Any]:
    checks = [
        check(
            "python",
            "pass" if sys.version_info >= (3, 10) else "fail",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
        tool_check("git", "git", required=True),
        identity_check(),
        cli_check(),
        *host_checks(),
        *mount_checks(),
    ]
    failed = sum(item["state"] == "fail" for item in checks)
    warned = sum(item["state"] == "warn" for item in checks)
    return {
        "schema": "pilot-puppy.doctor.v1",
        "product": "Pilot Puppy",
        "root": str(ROOT),
        "ok": failed == 0,
        "failed": failed,
        "warned": warned,
        "checks": checks,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="pilot-puppy doctor", description=__doc__)
    result.add_argument("--json", action="store_true", help="print machine-readable output")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = collect()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for item in report["checks"]:
            print(f"[{item['state'].upper()}] {item['name']}: {item['detail']}")
        print(f"{len(report['checks']) - report['failed']}/{len(report['checks'])} checks without hard failure; {report['warned']} warning(s)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
