#!/usr/bin/env python3
"""Generate full bake-off fixtures (48 total) from pilot templates."""

from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
FIXTURES = BASE / "fixtures"
ORACLES = BASE / "hidden-oracles"

STRATA = [
    ("atomic", "pilot-atomic-route-method", 8, "full-atomic"),
    ("compound", "pilot-compound-reconciliation", 10, "full-compound"),
    ("ui_runtime", "pilot-runtime-ui-proof", 8, "full-ui-runtime"),
    ("cold_resume", "pilot-cold-resume-dirty-wip", 4, "full-cold-resume-dirty"),
    ("cold_resume", "pilot-cold-resume-blocked-gate", 4, "full-cold-resume-blocked"),
    ("convergence", "pilot-convergence-stranded-branches", 6, "full-convergence"),
    ("safety", "pilot-safety-proof-honesty", 4, "full-safety"),
    ("plan_noise", "pilot-plan-noise-duplicate-trap", 4, "full-plan-noise"),
]


def fixture_id_for(prefix: str, template: str, index: int) -> str:
    if index == 1:
        return template
    return f"{prefix}-{index:02d}"


def clone_fixture(template_id: str, new_id: str, task_class: str, variant: int) -> dict:
    template = json.loads((FIXTURES / f"{template_id}.json").read_text(encoding="utf-8"))
    fixture = dict(template)
    fixture["fixture_id"] = new_id
    fixture["task_class"] = task_class
    fixture["start_commit"] = f"generated-full-v{variant}"
    fixture["setup_command"] = (
        f"BAKEOFF_WORKDIR=${{BAKEOFF_WORKDIR:?}} python3 evaluations/vidux-vs-native-bakeoff/scripts/setup_fixture.py "
        f"{new_id} \"$BAKEOFF_WORKDIR/{new_id}\""
    )
    fixture["task_prompt"] = fixture["task_prompt"] + f" Variant {variant}."
    fixture["hidden_acceptance_ref"] = f"hidden-oracles/{new_id}/manifest.json"
    return fixture


def write_oracle(new_id: str, template_id: str) -> None:
    src = ORACLES / template_id
    dst = ORACLES / new_id
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    manifest["fixture_id"] = new_id
    (dst / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    run_sh = textwrap.dedent(
        f"""
        #!/usr/bin/env bash
        set -euo pipefail
        ROOT="${{1:?run_cwd required}}"
        python3 "$(cd "$(dirname "$0")/../.." && pwd)/scripts/fixture_oracle.py" "{new_id}" "$ROOT"
        """
    ).lstrip()
    (dst / "run.sh").write_text(run_sh, encoding="utf-8")
    (dst / "run.sh").chmod(0o755)


def main() -> int:
    manifest: list[str] = []
    for task_class, template_id, count, prefix in STRATA:
        for idx in range(1, count + 1):
            new_id = fixture_id_for(prefix, template_id, idx)
            manifest.append(new_id)
            if new_id.startswith("pilot-") and (FIXTURES / f"{new_id}.json").exists():
                continue
            fixture = clone_fixture(template_id, new_id, task_class, idx)
            (FIXTURES / f"{new_id}.json").write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
            if not new_id.startswith("pilot-"):
                write_oracle(new_id, template_id)
    (FIXTURES / "full-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"generated {len(manifest)} fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
