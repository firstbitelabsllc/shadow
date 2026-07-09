# Vidux lifecycle doc convergence smoke - 2026-06-03

## Scope

Task: `5.3.0df Codex/Claude/Cursor lifecycle doc convergence`.

Goal: make setup and fleet docs describe one shared model for config readiness, runtime doctor use, plan/ledger proof, signpost traces, and spawned subagent call stacks across Codex, Claude, and Cursor-attributed workers.

## Drift found

- Fleet docs described Claude and Codex lifecycle details in separate runtime-specific shapes, while Cursor was not clearly named as an attributed worker runtime.
- Setup and operations docs did not consistently name the shared `vidux config check --json`, `scripts/vidux-doctor.sh --json`, `VIDUX_SIGNPOST_RUN_ID`, and signpost event sequence.
- README wording still made the model sound like a global single-tool prohibition instead of one primary writer runtime per lane with a shared proof spine.

## Files changed

- `README.md`
- `docs/fleet/index.md`
- `docs/fleet/platforms.md`
- `docs/fleet/claude-lifecycle.md`
- `docs/fleet/codex-lifecycle.md`
- `docs/fleet/codex-setup.md`
- `docs/fleet/operations.md`
- `tests/test_vidux_contracts.py`
- `PLAN.md`

## Proof

- `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_fleet_lifecycle_docs_share_config_doctor_signpost_contract tests.test_vidux_contracts.ViduxContractTests.test_interruption_and_fleet_docs_use_plan_ledger_recovery tests.test_vidux_contracts.ViduxContractTests.test_codex_runtime_recipes_scope_memory_to_lane_log` PASS, 3/3.
- `python3 -m unittest tests.test_signpost` PASS, 5/5.
- `npm run docs:build` PASS, VitePress build complete.
- `bin/vidux signpost lifecycle-smoke --run-id 5e30df-docs-smoke --json` PASS with 4 events.
- `bin/vidux signpost trace --run-id 5e30df-docs-smoke` PASS with ordered stack:
  - `hook.beforeTask` runtime `codex`, called `scripts/vidux-doctor.sh --json`
  - `subagent.spawn` runtime `claude`, called `spawned-worker`
  - `task.verify` runtime `cursor`, called `worker verify`
  - `hook.afterTask` runtime `codex`, called `vidux checkpoint`
- `git diff --check -- README.md docs/fleet/index.md docs/fleet/platforms.md docs/fleet/claude-lifecycle.md docs/fleet/codex-lifecycle.md docs/fleet/codex-setup.md docs/fleet/operations.md tests/test_vidux_contracts.py PLAN.md evidence/2026-06-03-vidux-lifecycle-doc-convergence-smoke.md` PASS.
- Publish ledger `evt_codex_20260603_5e30df_lifecycle_docs` verified in `~/.agent-ledger/activity.jsonl:5791`.
- `python3 scripts/vidux-publish-scrutiny.py --json ... --ledger evt_codex_20260603_5e30df_lifecycle_docs ...` PASS with `ready=true`.

## Contract repair note

The first broader contract run caught one wording regression: the lifecycle checkpoint lines used lowercase `update`, while the existing interruption recovery contract expects the exact phrase `Update the owning PLAN.md status/Progress and emit the matching publish ledger row`. The docs were corrected before the final PASS.

## Non-claims

- No real external Claude, Codex, or Cursor process was launched.
- No hook installer or recurring lane runner was installed or executed.
- No live `vidux.config.json` was created or mutated.
- No app repair, product repo mutation, local-CI execute, external mutation, stage, commit, push, PR, or upstream merge happened.
- The larger five-hour objective remains active after this row.
