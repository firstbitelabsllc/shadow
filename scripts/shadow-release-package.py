#!/usr/bin/env python3
"""Verify one small, public, installable Shadow release — a git checkout.

No npm since 2026-08-09: the clone IS the install (see install.sh), so this
verifies the tracked tree, not a packed tarball.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_version import read_version  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
# Provenance is the host plus the path, not a suffix: an attacker-controlled
# host serving `.../firstbitelabsllc/shadow.git` ends with the canonical path
# and must not pass as the canonical repository.
CANONICAL_ORIGIN = re.compile(
    r"(?:git\+)?(?:https?://|ssh://|git://)?(?:[^@/]+@)?github\.com[:/]"
    r"firstbitelabsllc/shadow(?:\.git)?/?",
    re.IGNORECASE,
)
# M26 adds the canonical plan-tree store, migration door, benchmark, and their
# checked-in contract. Keep a small explicit ceiling rather than letting the
# release grow without review.
MAX_FILE_COUNT = 120
MAX_UNPACKED_BYTES = 2_000_000
REQUIRED_FILES = {
    ".agents/plugins/marketplace.json",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "AGENT.md",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "SOURCE_REF",
    "SKILL.md",
    "skills/amplify/SKILL.md",
    "VERSION",
    "bin/shadow",
    "bin/shadow-browse",
    # Deleting either of these left the gate reporting publishable while
    # `shadow amp` and `shadow throw` exited 2 with "can't open file".
    "scripts/shadow-amp.py",
    "scripts/shadow-throw.py",
    "scripts/shadow_remote_claim.py",
    "scripts/shadow-return.py",
    "scripts/shadow-priority.py",
    "scripts/shadow-lifecycle.py",
    "scripts/shadow_board_import.py",
    "scripts/shadow_root_board.py",
    "scripts/shadow-host-directives.py",
    "scripts/shadow-slots.py",
    "scripts/shadow_config.py",
    "scripts/shadow-verify-host.sh",
    "scripts/shadow-verify-two-seat.py",
    "scripts/shadow_process_lib.py",
    "scripts/shadow_cmd_proof.py",
    "scripts/shadow_plan_grammar.py",
    "scripts/shadow-plan.py",
    "scripts/shadow_plan_store.py",
    "scripts/shadow_telemetry.py",
    "browser/chief_of_staff.py",
    "browser/decision_mode.py",
    "browser/outcome_source.py",
    "browser/server.py",
    "browser/static/app.js",
    "browser/static/index.html",
    "browser/static/style.css",
    "docs/reference/chief-of-staff.md",
    "docs/guide/publishing.md",
    "distribution/custom-gpt/instructions.md",
    "docs/reference/commands.md",
    "docs/reference/grammar.md",
    "docs/reference/method.md",
    "docs/reference/host-integration.md",
    "docs/reference/native-hosts.md",
    "docs/reference/telemetry.md",
    "docs/reference/outcome-choice.md",
    "examples/outcome-choice/example.json",
    "hooks/hooks.json",
    "schemas/chief-of-staff.v1.json",
    "schemas/decision-choice.v1.json",
    "schemas/decision-receipt.v1.json",
    "schemas/outcome-choice.v1.json",
    "schemas/retirement-manifest.v1.json",
    "scripts/shadow-doctor.py",
    "scripts/shadow-accept.py",
    "scripts/shadow-lint.py",
    "scripts/shadow-host.py",
    "scripts/shadow-init.py",
    "scripts/shadow-outcome-validate.py",
    "scripts/shadow-public-ready-grep-gate.py",
    "install.sh",
    "skills/amplify/references/amplify.md",
    "plugins/shadow/plugin.json",
    "plugins/shadow/.codex-plugin/plugin.json",
    "plugins/shadow/.claude-plugin/plugin.json",
    "plugins/shadow/skills/shadow/SKILL.md",
    "scripts/shadow-python.sh",
    "scripts/shadow-release-package.py",
    "scripts/shadow-status.py",
    "scripts/shadow-style-guard.py",
    "scripts/shadow_task_lib.py",
    "scripts/shadow_scrub_lib.py",
}
FORBIDDEN_ROOTS = {
    ".git",
    ".github",
    "node_modules",
    "tests",
    "test-results",
    "playwright-report",
}
FORBIDDEN_FILES = {"PLAN.md", "package-lock.json", ".gitleaks.toml", "playwright.config.ts", "vitest.config.mjs"}
FORBIDDEN_SUFFIXES = {".jsonl", ".key", ".log", ".pem", ".p12", ".token"}


def normalize(value: str) -> str:
    return PurePosixPath(value.replace("\\", "/").removeprefix("package/")).as_posix()


def source_version(root: Path) -> str:
    return read_version(root)


def release_notes(root: Path, version: str) -> str:
    """The tagged CHANGELOG section for `version`, refusing empty or absent.

    Measured 2026-08-18: shadow-v1.2.0 published with an EMPTY body because
    notes were hand-sliced from a checkout predating the release commit.
    Conduct generates notes from the checkout being released; an empty or
    missing section is a refusal, never a blank page.
    """
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    marker = f"\n## {version}"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"CHANGELOG.md has no section for {version}")
    body_start = text.index("\n", start + 1) + 1
    next_heading = text.find("\n## ", body_start)
    body = text[body_start : next_heading if next_heading >= 0 else len(text)]
    if len(body.strip()) < 40:
        raise ValueError(f"CHANGELOG.md section for {version} is empty")
    return body.strip() + "\n"


def changelog_version(root: Path) -> str:
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## ([0-9]+\.[0-9]+\.[0-9]+)\b", text, re.MULTILINE)
    if match is None:
        raise RuntimeError("CHANGELOG has no release heading")
    return match.group(1)


def inspect_release_identity(
    root: Path, version: str, *, require_release_ref: bool = False
) -> dict[str, Any]:
    """Bind public release identity to one namespaced annotated tag at HEAD."""
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        raise ValueError("VERSION is not semantic x.y.z")
    head = command(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD^{commit}"], root
    ).stdout.strip()
    expected = f"shadow-v{version}"
    ref = f"refs/tags/{expected}"
    present = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", "--quiet", ref],
        capture_output=True,
        check=False,
    ).returncode == 0
    errors: list[str] = []
    release_ref = None
    if present:
        object_type = command(["git", "-C", str(root), "cat-file", "-t", ref], root).stdout.strip()
        if object_type != "tag":
            if require_release_ref:
                errors.append(f"public release tag {expected} must be annotated")
        else:
            tagged = command(
                ["git", "-C", str(root), "rev-parse", "--verify", f"{ref}^{{commit}}"], root
            ).stdout.strip()
            if tagged != head:
                if require_release_ref:
                    errors.append(f"public release tag {expected} must resolve to exact HEAD")
            else:
                release_ref = expected
    elif require_release_ref:
        errors.append(f"public release requires annotated tag {expected} at exact HEAD")
    return {"commit": head, "release_ref": release_ref, "errors": errors}


def forbidden(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        not pure.parts
        or pure.parts[0] in FORBIDDEN_ROOTS
        or path in FORBIDDEN_FILES
        or "__pycache__" in pure.parts
        or any(part.startswith(".env") for part in pure.parts)
        or pure.suffix.lower() in FORBIDDEN_SUFFIXES
    )


def validate_release_candidate(
    plugin: dict[str, Any],
    pack: dict[str, Any],
    *,
    version: str,
    tracked_paths: Iterable[str],
    dirty_paths: Iterable[str] = (),
    allow_dirty: bool = False,
    expected_version: str | None = None,
) -> list[str]:
    errors = []
    files = {normalize(str(item["path"])) for item in pack.get("files", []) if item.get("path")}
    tracked = {normalize(path) for path in tracked_paths}
    dirty = sorted(files & {normalize(path) for path in dirty_paths})
    wanted_version = expected_version or version
    if expected_version and version != expected_version:
        errors.append("VERSION does not match --expect-version")
    if plugin.get("name") != "shadow":
        errors.append("plugin must be named shadow")
    if plugin.get("version") != wanted_version or pack.get("version") != wanted_version:
        errors.append("plugin, archived artifact, and VERSION must match")
    if not CANONICAL_ORIGIN.fullmatch(str(pack.get("origin", "")).strip()):
        errors.append("release must be cut from the canonical public repository")
    missing = sorted(REQUIRED_FILES - files)
    if missing:
        errors.append("archived artifact is missing: " + ", ".join(missing))
    blocked = sorted(path for path in files if forbidden(path))
    if blocked:
        errors.append("archived artifact contains forbidden files: " + ", ".join(blocked))
    skills = sorted(path for path in files if PurePosixPath(path).name == "SKILL.md")
    expected_skills = ["SKILL.md", "plugins/shadow/skills/shadow/SKILL.md", "skills/amplify/SKILL.md"]
    if skills != expected_skills:
        errors.append("archived artifact must contain exactly the native, portable, and amplify skills")
    untracked = sorted(files - tracked)
    if untracked and not allow_dirty:
        errors.append("archived artifact contains untracked files: " + ", ".join(untracked))
    if dirty and not allow_dirty:
        errors.append("archived artifact contains uncommitted bytes: " + ", ".join(dirty))
    if len(files) > MAX_FILE_COUNT:
        errors.append(f"archived artifact exceeds {MAX_FILE_COUNT} files")
    if int(pack.get("unpackedSize", 0) or 0) > MAX_UNPACKED_BYTES:
        errors.append(f"archived artifact exceeds {MAX_UNPACKED_BYTES} unpacked bytes")
    return errors


def command(
    command: list[str], cwd: Path, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, check=False
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return result


def tracked_files(root: Path) -> set[str]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("git ls-files failed")
    return {item.decode("utf-8") for item in result.stdout.split(b"\0") if item}


def dirty_files(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("git status failed")
    paths = set()
    rows = [row for row in result.stdout.split(b"\0") if row]
    index = 0
    while index < len(rows):
        row = rows[index].decode("utf-8", errors="surrogateescape")
        paths.add(row[3:])
        if row[:2] in {"R ", "C ", "RM", "CM"} and index + 1 < len(rows):
            index += 1
            paths.add(rows[index].decode("utf-8", errors="surrogateescape"))
        index += 1
    return paths


def pack(
    root: Path, destination: Path, *, source_ref: str = "HEAD"
) -> tuple[dict[str, Any], Path, str]:
    """Reproducible archive of the TRACKED tree via git — no packer, no manifest
    format, no package manager. The clone is the install, so the release
    artifact is simply what git would hand a stranger."""
    version = source_version(root)
    tarball = destination / f"shadow-{version}.tar"
    command(
        ["git", "-C", str(root), "archive", "--format=tar",
         f"--output={tarball}", source_ref],
        root,
    )
    listing = command(["tar", "-tf", str(tarball)], root).stdout.split("\n")
    files = [{"path": name} for name in listing if name and not name.endswith("/")]
    origin = command(["git", "-C", str(root), "config", "--get", "remote.origin.url"], root).stdout.strip()
    manifest = {"files": files, "version": version, "origin": origin,
                "unpackedSize": sum((root / f["path"]).stat().st_size
                                    for f in files if (root / f["path"]).is_file())}
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    return manifest, tarball, digest


def commit_disposable_fixture(project: Path) -> None:
    """Seed the stranger-install repo without leaving Git maintenance behind."""
    command(
        [
            "git",
            "-c",
            "maintenance.autoDetach=false",
            "-c",
            "gc.autoDetach=false",
            "commit",
            "--quiet",
            "-m",
            "seed installed lifecycle",
        ],
        project,
    )


def stranger_install(tarball: Path, root: Path, expected_version: str) -> None:
    """Prove a stranger can install from the archive with Git, Bash, Python —
    exactly the path install.sh documents."""
    consumer = root / "consumer"
    consumer.mkdir()
    command(["tar", "-xf", str(tarball), "-C", str(consumer)], root)
    bin_dir = root / "bin"
    bin_dir.mkdir()
    home = root / "home"
    home.mkdir()
    for host in (".claude", ".agents", ".cursor", ".codex", ".grok"):
        (home / host).mkdir()
    native_host = bin_dir / "codex"
    native_host.write_text("#!/bin/sh\nprintf 'codex stranger-proof\\n'\n", encoding="utf-8")
    native_host.chmod(0o755)
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
    })
    command(
        ["bash", str(consumer / "install.sh"), "--bin-dir", str(bin_dir)],
        consumer,
        env=env,
    )
    cli = bin_dir / "shadow"
    version = command([str(cli), "--version"], consumer, env=env).stdout.strip()
    if version != expected_version:
        raise RuntimeError("installed command version does not match source")
    if source_version(consumer) != expected_version or changelog_version(consumer) != expected_version:
        raise RuntimeError("installed VERSION and top changelog release do not match")
    plugin = json.loads((consumer / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if plugin.get("version") != expected_version:
        raise RuntimeError("installed plugin version does not match source")
    goal = command([str(cli), "goal"], consumer, env=env).stdout
    for clause in ("~/.shadow", "project → entity → milestone → checkpoint", "shadow status --by"):
        if clause not in goal:
            raise RuntimeError(f"installed standing goal lost: {clause}")
    expected_help = {
        "config": ("--explain", "shadow.yaml"),
        "status": ("--by OWNER", "--in-flight"),
        "amp": ("--entity ID", "--by OWNER"),
        "throw": ("--entity ID", "--by OWNER"),
        "return": ("--entity ID", "--by OWNER"),
        "accept": ("--by OWNER", "--row '~hash'"),
        "lifecycle": (
            "--apply",
            "--milestone 'exact heading'",
            "--retirement-manifest /ABS/manifest.json",
            "--expect CAS",
            "--by SEAT",
        ),
    }
    for verb, clauses in expected_help.items():
        output = command([str(cli), "help", verb], consumer, env=env).stdout
        for clause in clauses:
            if clause not in output:
                raise RuntimeError(f"installed help {verb} lost: {clause}")
    for mount in (
        home / ".claude" / "skills" / "shadow",
        home / ".agents" / "skills" / "shadow",
        home / ".cursor" / "skills" / "shadow",
        home / ".grok" / "skills" / "shadow",
    ):
        if not mount.is_symlink() or mount.resolve() != consumer.resolve():
            raise RuntimeError(f"installed skill mount is missing or stale: {mount.parent.parent.name}")
    for instructions in (
        home / ".claude" / "CLAUDE.md",
        home / ".codex" / "AGENTS.md",
        home / ".grok" / "AGENTS.md",
    ):
        text = instructions.read_text(encoding="utf-8")
        if goal.strip() not in text or text.count("<!-- shadow:goal:begin") != 1:
            raise RuntimeError("installed host instructions lost the managed standing goal")
    doctor = json.loads(command([str(cli), "doctor", "--json"], consumer, env=env).stdout)
    if not doctor.get("ok"):
        raise RuntimeError("installed doctor did not accept the stranger installation")
    two_seat = json.loads(command(
        [
            str(consumer / "scripts" / "shadow-python.sh"),
            str(consumer / "scripts" / "shadow-verify-two-seat.py"),
            "--json",
        ],
        consumer,
        env=env,
    ).stdout)
    if (
        two_seat.get("schema") != "shadow.two-seat-verification.v1"
        or two_seat.get("status") != "pass"
        or two_seat.get("mode") != "offline"
        or two_seat.get("board", {}).get("completed") != 2
        or two_seat.get("board", {}).get("claims") != 0
    ):
        raise RuntimeError("installed two-seat harness did not complete its offline proof")
    project = root / "installed-project"
    project.mkdir()
    command(["git", "init", "--quiet"], project)
    command(["git", "config", "user.name", "Shadow Stranger"], project)
    command(["git", "config", "user.email", "shadow-stranger@example.invalid"], project)
    (project / "PLAN.md").write_text(
        "# Project\n\n"
        "## Brief\n\n"
        "- Project: stranger-proof\n"
        "- Mode: ship\n"
        "- Priority: 2\n\n"
        "## Tasks\n\n"
        "### Installed lifecycle\n"
        "- [pending] claim and prove through the installed command ~aa11 | proof: cmd true\n"
        "- [pending] return remains owner-safe ~bb22 (DoD) | proof: cmd true | needs: ~aa11\n\n"
        "## Progress\n\n"
        "- 2026-08-10T00:00:00Z NOTE stranger install fixture\n",
        encoding="utf-8",
    )
    command(["git", "add", "PLAN.md"], project)
    commit_disposable_fixture(project)
    lifecycle_env = {**env, "SHADOW_PORTFOLIO_ROOT": str(project)}
    command([str(cli), "status", "--root", str(project), "--by", "release-seat", "--json"], project, env=lifecycle_env)
    command([str(cli), "throw", "--repo", str(project), "--task", "~aa11", "--by", "release-seat"], project, env=lifecycle_env)
    packet = command([str(cli), "amp", "--repo", str(project), "--task", "~aa11", "--by", "release-seat"], project, env=lifecycle_env).stdout
    if "/goal" not in packet:
        raise RuntimeError("installed claim did not produce its owned packet")
    command([str(cli), "accept", "--repo", str(project), "--row", "~aa11", "--by", "release-seat", "--no-push"], project, env=lifecycle_env)
    command([str(cli), "throw", "--repo", str(project), "--task", "~bb22", "--by", "release-seat"], project, env=lifecycle_env)
    command([str(cli), "return", "--repo", str(project), "--row", "~bb22", "--by", "release-seat"], project, env=lifecycle_env)
    board = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
    if board["claims"]:
        raise RuntimeError("installed lifecycle left a claim behind")
    completed = (project / "PLAN.md").read_text(encoding="utf-8")
    if "[completed] claim and prove" not in completed or "~aa11 PROOF" not in completed:
        raise RuntimeError("installed accept did not persist its completion proof")


def verify(
    root: Path,
    *,
    expected_version: str | None = None,
    allow_dirty: bool = False,
    require_release_ref: bool = False,
) -> dict[str, Any]:
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    version = source_version(root)
    identity = inspect_release_identity(
        root, version, require_release_ref=require_release_ref
    )
    with tempfile.TemporaryDirectory(prefix="shadow-release-") as dirname:
        temp = Path(dirname)
        first = temp / "first"
        second = temp / "second"
        first.mkdir()
        second.mkdir()
        manifest, tarball, first_sha = pack(
            root, first, source_ref=identity["commit"]
        )
        second_manifest, _, second_sha = pack(
            root, second, source_ref=identity["commit"]
        )
        errors = validate_release_candidate(
            plugin,
            manifest,
            version=version,
            tracked_paths=tracked_files(root),
            dirty_paths=dirty_files(root),
            allow_dirty=allow_dirty,
            expected_version=expected_version,
        )
        errors.extend(identity["errors"])
        if require_release_ref:
            final_identity = inspect_release_identity(
                root, version, require_release_ref=True
            )
            if final_identity != identity:
                errors.append("public release identity changed during verification")
        if require_release_ref and allow_dirty:
            errors.append("public release mode cannot allow dirty bytes")
        if first_sha != second_sha or manifest.get("files") != second_manifest.get("files"):
            errors.append("repeated git archive runs are not reproducible")
        install_ok = False
        if not errors:
            stranger_install(tarball, temp, version)
            install_ok = True
    dirty = sorted(dirty_files(root))
    return {
        "schema": "shadow.release.v1",
        "ok": not errors,
        "publishable": (
            require_release_ref and not errors and not dirty and not allow_dirty
        ),
        "version": version,
        "commit": identity["commit"],
        "release_ref": identity["release_ref"],
        "file_count": len(manifest.get("files", [])),
        "unpacked_bytes": int(manifest.get("unpackedSize", 0) or 0),
        "sha256": first_sha,
        "reproducible": first_sha == second_sha,
        "stranger_install": install_ok,
        "dirty_files": dirty,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--expect-version")
    parser.add_argument(
        "--notes",
        action="store_true",
        help="print the CHANGELOG section for the source version and exit; "
        "an empty or missing section exits nonzero",
    )
    parser.add_argument("--allow-dirty", action="store_true", help="allow a non-publishable development receipt")
    parser.add_argument(
        "--public-release",
        action="store_true",
        help="require the annotated shadow-v<version> tag at exact HEAD",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.notes:
        try:
            sys.stdout.write(release_notes(args.root, source_version(args.root)))
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"release notes refused: {exc}", file=sys.stderr)
            return 1
        return 0
    try:
        report = verify(
            args.root.resolve(),
            expected_version=args.expect_version,
            allow_dirty=args.allow_dirty,
            require_release_ref=args.public_release,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        report = {"schema": "shadow.release.v1", "ok": False, "publishable": False, "errors": [str(exc)]}
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["ok"]:
        print(f"shadow release package: OK ({report['version']}, {report['file_count']} files, sha256={report['sha256']})")
    else:
        print("shadow release package: FAILED", file=sys.stderr)
        for error in report["errors"]:
            print(f"- {error}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
