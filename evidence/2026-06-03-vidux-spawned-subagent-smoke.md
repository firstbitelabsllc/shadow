# Vidux spawned-subagent smoke

Date: 2026-06-03
Task: 5.3.0di Spawned-subagent smoke plan
Lane: vidux-five-hour-observability

## What changed

- Added `vidux signpost spawned-subagent-smoke`.
- The smoke uses temporary local environment overlays to simulate:
  - Codex parent beforeTask with `CODEX_SESSION_ID` and `CODEX_THREAD_ID`.
  - Claude spawned worker with inherited `CODEX_THREAD_ID`, `VIDUX_RUNTIME=claude`, and `CLAUDE_SESSION_ID`.
  - Cursor verification worker with inherited `CODEX_THREAD_ID`, `VIDUX_RUNTIME=cursor`, and `CURSOR_SESSION_ID`.
  - Codex parent afterTask.
- `trace_events` now includes `thread_id` and `automation_id` so attribution proof is visible in the operator trace output.
- Updated CLI help, shell completion, README, fleet docs, hook docs, command docs, and script reference.

## Proof

- `python3 -m py_compile scripts/vidux_signpost.py tests/test_signpost.py tests/test_vidux_contracts.py` PASS.
- `python3 -m unittest tests.test_signpost` PASS, 6/6.
- `bash -n bin/vidux scripts/vidux-completion.sh` PASS.
- Initial lifecycle contract rerun used the wrong class name and failed with `AttributeError: module 'tests.test_vidux_contracts' has no attribute 'ViduxContractsTest'`; corrected command below passed.
- `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_fleet_lifecycle_docs_share_config_doctor_signpost_contract` PASS, 1/1.
- `bin/vidux help signpost` PASS and lists `spawned-subagent-smoke`.
- `bin/vidux signpost spawned-subagent-smoke --run-id 5e30di-subagent-smoke --json` PASS, 4/4 events in `~/.vidux/signposts.jsonl`.
- `bin/vidux signpost trace --run-id 5e30di-subagent-smoke` PASS with ordered `hook.beforeTask` Codex, `subagent.spawn` Claude, `task.verify` Cursor, `hook.afterTask` Codex.
- `/tmp` fixture smoke PASS:

```bash
rm -f /tmp/vidux-5e30di-subagent-signposts.jsonl
bin/vidux signpost spawned-subagent-smoke \
  --log /tmp/vidux-5e30di-subagent-signposts.jsonl \
  --run-id 5e30di-fixture-subagent-smoke \
  --json
```

- Fixture trace PASS:

```text
trace events: 4 (/tmp/vidux-5e30di-subagent-signposts.jsonl, run_id=5e30di-fixture-subagent-smoke)
- #1 2026-06-03T04:34:29.906762Z 5e30di-fixture-subagent-smoke hook.beforeTask status=ok runtime=codex called=scripts/vidux-doctor.sh --json
- #2 2026-06-03T04:34:29.907762Z 5e30di-fixture-subagent-smoke subagent.spawn status=ok runtime=claude called=claude spawned-worker
- #3 2026-06-03T04:34:29.908762Z 5e30di-fixture-subagent-smoke task.verify status=ok runtime=cursor called=cursor worker verify
- #4 2026-06-03T04:34:29.909762Z 5e30di-fixture-subagent-smoke hook.afterTask status=ok runtime=codex called=vidux checkpoint
```

- `npm run docs:build` PASS.
- Scoped `git diff --check` PASS for the changed signpost/docs/test/help surface.
- First publish-scrutiny run failed closed with `missing_fields=["claims"]`; rerun with mirrored `--claim` fields PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30di_spawned_subagent_smoke` verified in `~/.agent-ledger/activity.jsonl:5794`.

## Non-claims

- No real Claude, Codex, or Cursor external runtime was launched.
- No hook installer or hook runner was added.
- No config was created or mutated.
- No local-CI lane was executed.
- No external board, GitHub, product repo, browser mutation, stage, commit, push, or PR action was performed.
