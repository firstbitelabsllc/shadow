#!/usr/bin/env python3
"""Read-only Shadow installation doctor."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(os.environ.get("SHADOW_ROOT", Path(__file__).resolve().parent.parent)).resolve()
HOSTS = ("codex", "claude-code", "cursor")
MOUNTS = (
    Path.home() / ".claude" / "skills" / "shadow",
    Path.home() / ".agents" / "skills" / "shadow",
    Path.home() / ".cursor" / "skills" / "shadow",
)


def check(name: str, state: str, detail: str, **data: Any) -> dict[str, Any]:
    return {"name": name, "state": state, "detail": detail, **data}


def identity_check() -> dict[str, Any]:
    # No package.json since 2026-08-09: VERSION and the plugin manifest are
    # the only identity sources, and they must agree.
    try:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, IndexError) as exc:
        return check("product identity", "fail", f"metadata is unreadable: {exc}")
    valid = (
        plugin.get("name") == "shadow"
        and plugin.get("version") == version
        and (ROOT / "SKILL.md").is_file()
        and (ROOT / "AGENT.md").is_file()
        and (ROOT / "bin" / "shadow").is_file()
    )
    return check(
        "product identity",
        "pass" if valid else "fail",
        f"shadow {version}" if valid else "plugin, skill, command, and version disagree",
        version=version,
    )


def tool_check(name: str, executable: str, *, required: bool) -> dict[str, Any]:
    path = shutil.which(executable)
    if path:
        return check(name, "pass", str(Path(path).resolve()), executable=executable)
    return check(name, "fail" if required else "warn", f"{executable} is not on PATH", executable=executable)


def cli_check() -> dict[str, Any]:
    path = shutil.which("shadow")
    if not path:
        return check("PATH command", "warn", "shadow is not installed on PATH")
    expected = Path(os.environ.get("SHADOW_DOCTOR_EXPECTED_CLI", ROOT / "bin" / "shadow")).resolve()
    actual = Path(path).resolve()
    if actual != expected:
        return check("PATH command", "fail", f"resolves to {actual}, expected {expected}")
    return check("PATH command", "pass", str(actual))


def host_checks() -> list[dict[str, Any]]:
    script = ROOT / "scripts" / "shadow-host.py"
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


def standing_goal() -> str:
    """The static block, read from the doc that ships it — the same extraction
    `shadow goal` performs, so the command and this check cannot disagree."""
    try:
        lines = (ROOT / "docs" / "reference" / "host-integration.md").read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError:
        return ""
    out: list[str] = []
    for line in lines:
        if line.startswith("## Shadow "):
            out.append(line)
        elif out:
            if line == "```":
                break
            out.append(line)
    return "\n".join(out).strip()


def host_goal_checks() -> list[dict[str, Any]]:
    """Whether each host's instruction file carries the current standing goal.

    Without this, drift is undetectable: three semantic mutations of the block
    (a renamed flag, a renamed verb, the stance inverted to "ask the person
    which project") each passed the whole suite and shipped, because no
    executable read a host file. Read-only — it repairs nothing.

    Cursor is absent on purpose: its user rules live in application settings,
    not a file, so asserting a path here would invent a convention.
    """
    block = standing_goal()
    if not block:
        return [check("standing goal: source", "fail", "no block found in docs/reference/host-integration.md")]
    anchor = block.splitlines()[0]
    results = []
    for label, path in (("claude", Path.home() / ".claude" / "CLAUDE.md"),
                        ("codex", Path.home() / ".codex" / "AGENTS.md")):
        name = f"standing goal: {label}"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            # A missing host file is that host not being configured, not a
            # broken install — warn, never fail. Still say the fix: a warning
            # a person cannot act on is noise.
            results.append(check(name, "warn", "no host instruction file — create it with: shadow goal --install"))
            continue
        # Count first. `block in text` is a bare substring test, so a file
        # holding a stale copy AND a fresh one appended below it passed as
        # "current" — while the host reads the stale one first. That is exactly
        # what happened to anyone who followed the old remedy, which said
        # `shadow goal >> <file>`: append, two blocks, green, wrong.
        copies = text.count(anchor)
        if copies > 1:
            results.append(check(
                name, "fail",
                f"{copies} copies of the standing goal — the host reads the first one; "
                "delete the extras, then: shadow goal --install",
            ))
        elif block in text:
            results.append(check(name, "pass", "current"))
        elif copies == 1:
            results.append(check(name, "fail", "stale copy — replace it with: shadow goal --install"))
        else:
            results.append(check(name, "warn", "not pasted — add it with: shadow goal --install"))
    return results


def bucket_checks() -> list[dict[str, Any]]:
    """Which extension buckets are filled. Read-only, derived, never stored."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "shadow_buckets", ROOT / "scripts" / "shadow-buckets.py"
    )
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module.checks()
    except OSError:
        return []


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
        *host_goal_checks(),
        *bucket_checks(),
    ]
    failed = sum(item["state"] == "fail" for item in checks)
    warned = sum(item["state"] == "warn" for item in checks)
    return {
        "schema": "shadow.doctor.v1",
        "product": "Shadow",
        "root": str(ROOT),
        "ok": failed == 0,
        "failed": failed,
        "warned": warned,
        "checks": checks,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="shadow doctor", description=__doc__)
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
