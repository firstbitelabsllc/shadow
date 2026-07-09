# Vidux command and skill drift smoke

Date: 2026-06-03
Task: 5.3.0ee Command and skill drift smoke after argv sweep
Lane: vidux-five-hour-observability

## Scope

Post-argv-sweep command and app-adjacent smoke pass:

- Re-run install doctor, runtime doctor, config, signpost, status, browser/HTTP, and docs surfaces.
- Preserve runtime warnings separately from command pass/fail status.
- Fix stale `/amp` and `/auto` Leo-private skill wording caught by Vidux contract tests.

## Command Surface Proof

| Surface | Result | Notes |
| --- | --- | --- |
| Install doctor | PASS | `VIDUX_DOCTOR_SKIP_NPM_TEST=1 bin/vidux doctor` passed 7/7. |
| Runtime doctor | WARN | `scripts/vidux-doctor.sh --json` passed 11/14 checks. Warnings: `orphan_automations` count 2 (`codex-plans-auditor`, `strongyes-10m-cleanup`), `stale_in_progress` count 6, `bimodal_runtime` count 5. |
| Status board | PASS | `bin/vidux status --root ~/Development/vidux --focus vidux --json` returned the root plan with pending 3, in_progress 0, completed 148, blocked 1. |
| Config check | PASS | `bin/vidux config check --json` returned `status=ok`, `source=example`, `live_config_present=false`, redacted token metadata, and no issues. |
| Lifecycle signpost | PASS | `bin/vidux signpost lifecycle-smoke --json` emitted 4 ordered events: codex beforeTask, claude spawn, cursor verify, codex afterTask. |
| Spawned-subagent signpost | PASS | `bin/vidux signpost spawned-subagent-smoke --json` emitted 4 ordered events with inherited Codex thread attribution for Claude/Cursor worker simulation. |
| Browser JS syntax | PASS | `node --check browser/static/app.js` and `node --check browser/static/readaloud.js` passed. |
| HTTP monitor, wrong route | FAIL/WARN as designed | `bin/vidux http-smoke --json --timeout 1 ... http://127.0.0.1:8765/` returned Vidux root pass, Litty `/workers` `warn_partial`, and Voxtral root `fail_http` 404. |
| HTTP monitor, corrected route | PASS | `bin/vidux http-smoke --json --timeout 3 ... http://127.0.0.1:8765/health` passed Vidux root, Litty `/workers`, and Voxtral `/health` with `ok=true`, `strict_ok=true`, `warn_count=0`, `fail_count=0`. |

## Bug Found And Fixed

The focused post-sweep suite initially failed:

```text
python3 -m unittest tests.test_browser_server tests.test_vidux_config_cli tests.test_signpost tests.test_http_smoke tests.test_vidux_contracts
Ran 279 tests in 154.910s
FAILED (failures=4)
```

The failing contracts caught stale Leo-private skill wording:

- `~/<private-skill-root>/skills/amp/SKILL.md` still framed Harness Mode state as `PLAN.md`, evidence, and `memory.md`.
- `~/<private-skill-root>/skills/auto/SKILL.md` still told agents to commit and push the ai repo after observed-decision capture.
- `~/<private-skill-root>/skills/auto/SKILL.md` still called auto-dream `memory.md` a durable cycle log.

Fixes:

- `/amp` now says state orientation lives in the owning PLAN, evidence files, matching publish ledger rows, and lane-local memory notes; shipped-work proof/resume belongs to the plan plus publish ledger packet.
- `/auto` shared-tooling and evolution rules now require the owning PLAN plus publish ledger packet before git transport, including proof, handoff_status, files claimed, changed-file claims, and next-agent resume.
- `/auto` auto-dream memory is now lane-local weak-signal and cycle-orientation only.

## Regression Proof

- Stale skill grep PASS with no hits:
  `rg -n 'State lives in PLAN\\.md|state lives in files|state lives in the PLAN\\.md|\\+ commit SHA|\\[Evidence: <proof/SHA>\\]|Commit \\+ push the ai repo per \`/captain\` rules|durable cycle log|STOP, commit \\+ push|The local edit IS the bug|commit IS the fix' ~/<private-skill-root>/skills/amp/SKILL.md ~/<private-skill-root>/skills/auto/SKILL.md`
- Focused skill drift contracts PASS 4/4:
  `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_amp_harness_goal_mode_uses_plan_ledger_state tests.test_vidux_contracts.ViduxContractTests.test_auto_shared_tooling_pushes_use_plan_ledger_packet tests.test_vidux_contracts.ViduxContractTests.test_auto_evolution_rules_use_publish_packet_before_ai_repo_sync tests.test_vidux_contracts.ViduxContractTests.test_auto_dream_memory_is_lane_local_orientation`
- Broader rerun PASS 279/279:
  `python3 -m unittest tests.test_browser_server tests.test_vidux_config_cli tests.test_signpost tests.test_http_smoke tests.test_vidux_contracts`
- `npm run docs:build` PASS.
- `git -C ~/Development/ai-leo diff --check -- skills/amp/SKILL.md skills/auto/SKILL.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30ee_command_skill_drift_smoke` verified at `~/.agent-ledger/activity.jsonl:5850`.

## Non-claims

- Runtime doctor warnings were not repaired.
- No orphan automation cleanup, stale in-progress cleanup, bimodal-runtime repair, hook install, runtime doctor `--fix`, live config creation, local-CI execute, external service mutation, stage, commit, push, or PR was performed.
- The Voxtral root 404 is not a service-down claim; the documented readiness route is `/health`, which passed.
