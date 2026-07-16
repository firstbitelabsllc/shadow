#!/usr/bin/env python3
"""Verify the Vidux/native bake-off package is internally runnable."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
FIXTURE_DIR = BASE / "fixtures"
ORACLE_DIR = BASE / "hidden-oracles"
SCRIPT_DIR = BASE / "scripts"


REQUIRED_PROTOCOL_TERMS = [
    "Cursor Native",
    "Claude Native",
    "Codex Native",
    "Current Vidux",
    "Thin Vidux Kernel",
    "Mechanical Oracles",
    "Blinded 20-Reviewer Rubric",
    "Keep Current Vidux",
    "Kernelize Vidux",
    "Cut Or Bypass Vidux",
    "Falsification Tests",
]


REQUIRED_FIXTURE_KEYS = {
    "fixture_id",
    "task_class",
    "repo",
    "start_commit",
    "setup_command",
    "task_prompt",
    "visible_acceptance",
    "hidden_acceptance_ref",
    "allowed_paths",
    "forbidden_paths",
    "required_proof_commands",
    "real_surface_proof",
    "forbidden_actions",
    "expected_artifacts",
    "reviewer_packet_rule",
    "cleanup_rule",
}


def fail(message: str) -> None:
    raise SystemExit(f"VERIFY_FAIL: {message}")


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail(f"{path} is invalid JSON: {exc}")


def verify_protocol() -> None:
    text = (BASE / "PROTOCOL.md").read_text(encoding="utf-8")
    for term in REQUIRED_PROTOCOL_TERMS:
        if term not in text:
            fail(f"PROTOCOL.md missing {term!r}")


def verify_arm_prompts() -> None:
    prompts = {
        "cursor-native.md",
        "claude-native.md",
        "codex-native.md",
        "current-vidux.md",
        "thin-vidux-kernel.md",
    }
    found = {p.name for p in (BASE / "arm-prompts").glob("*.md")}
    missing = prompts - found
    if missing:
        fail(f"missing arm prompts: {sorted(missing)}")


def verify_fixture_files() -> list[dict]:
    fixtures = []
    for path in sorted(FIXTURE_DIR.glob("pilot-*.json")):
        data = load_json(path)
        missing = REQUIRED_FIXTURE_KEYS - set(data)
        if missing:
            fail(f"{path.name} missing keys: {sorted(missing)}")
        if data["fixture_id"] != path.stem:
            fail(f"{path.name} fixture_id mismatch: {data['fixture_id']}")
        oracle_path = ORACLE_DIR / data["fixture_id"] / "run.sh"
        manifest_path = ORACLE_DIR / data["fixture_id"] / "manifest.json"
        if not oracle_path.exists():
            fail(f"{data['fixture_id']} missing hidden oracle run.sh")
        if not manifest_path.exists():
            fail(f"{data['fixture_id']} missing hidden oracle manifest.json")
        manifest = load_json(manifest_path)
        if manifest.get("fixture_id") != data["fixture_id"]:
            fail(f"{data['fixture_id']} oracle manifest fixture_id mismatch")
        if manifest.get("seeded_bad_expected") != "fail":
            fail(f"{data['fixture_id']} oracle manifest must expect seeded bad failure")
        fixtures.append(data)
    if len(fixtures) != 8:
        fail(f"expected 8 pilot fixtures, found {len(fixtures)}")
    return fixtures


def verify_seeded_bad_states_fail(fixtures: list[dict]) -> None:
    setup = SCRIPT_DIR / "setup_pilot_fixture.py"
    for fixture in fixtures:
        fixture_id = fixture["fixture_id"]
        with tempfile.TemporaryDirectory(prefix=f"{fixture_id}-") as tmp:
            repo_dir = Path(tmp) / "repo"
            created = run(["python3", str(setup), fixture_id, str(repo_dir)], BASE)
            if created.returncode != 0:
                fail(f"{fixture_id} setup failed: {created.stderr}")
            visible = run(["python3", "checks/visible_check.py"], repo_dir)
            if visible.returncode != 0:
                fail(f"{fixture_id} visible check failed on seeded start: {visible.stderr}")
            oracle = ORACLE_DIR / fixture_id / "run.sh"
            result = run(["bash", str(oracle), str(repo_dir)], BASE)
            if result.returncode == 0:
                fail(f"{fixture_id} hidden oracle unexpectedly passed seeded bad state")


def main() -> int:
    verify_protocol()
    verify_arm_prompts()
    fixtures = verify_fixture_files()
    verify_seeded_bad_states_fail(fixtures)
    print("VERIFY_OK: protocol package has 8 fixtures and seeded bad states fail hidden oracles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
