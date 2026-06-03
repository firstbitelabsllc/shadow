# Vidux Config, Doctor, Signpost Trace Smoke

Date: 2026-06-03
Task: 5.3.0da

## Scope

First slice of the five-hour Vidux observability/config/app-smoke push:

- Add a user-facing `vidux config` CLI.
- Make `vidux doctor` validate config shape.
- Add ordered signpost trace proof for pre/during/post hook and spawned-subagent events.
- Fix docs drift around local-only `vidux.config.json`.
- Smoke the CLI, signpost trace, docs build, browser-adjacent test surface, and configured test bundle.

## Bugs Found

1. Signpost runtime attribution drift:
   - First smoke emitted Codex, Claude, and Cursor-looking events, but all were attributed as `codex`.
   - Cause: ambient Codex thread/session environment won over explicit spawned-worker markers.
   - Fix: `VIDUX_RUNTIME` override now wins; Claude/Cursor markers beat ambient Codex thread markers.
   - Proof: corrected trace smoke shows `runtime=codex`, `runtime=claude`, `runtime=cursor` in order.

2. Browser read-aloud static contract drift:
   - First broad `npm test` run failed two `tests.test_browser_server` read-aloud contracts.
   - Cause: source/fixture had already moved to 16 fixture states and newer offline/batch wording, while tests still expected 15 states and stale strings.
   - Fix: static contract now matches the current `readaloud-fixture-manifest.json`, fixture HTML, and `readaloud.js` wording.
   - Proof: `python3 -m unittest tests.test_browser_server` passes 40/40; rerun `npm test` passes.

## Command Evidence

```text
python3 -m py_compile scripts/vidux-config.py scripts/vidux_signpost.py
PASS

bash -n bin/vidux scripts/vidux-doctor-cli.sh scripts/vidux-completion.sh
PASS

python3 -m unittest tests.test_vidux_config_cli tests.test_signpost
Ran 9 tests in 0.690s
OK

bin/vidux config check --json
status=ok source=example live_config_present=false using_example=true plan_store.path_exists=true inbox_sources_total=1

bin/vidux config show
vidux config check: ok
source: example (/Users/leokwan/Development/vidux/vidux.config.example.json)
live config: missing; using checked-in example
plan_store: local /Users/leokwan/Development/vidux/projects (exists)
inbox_sources: 1 total, 1 enabled

VIDUX_DOCTOR_SKIP_NPM_TEST=1 bin/vidux doctor
7/7 checks passed

bin/vidux signpost trace --run-id smoke-20260603-config-trace-fixed --json
events=3
sequence: hook.beforeTask runtime=codex
sequence: subagent.spawn runtime=claude
sequence: hook.afterTask runtime=cursor

python3 -m unittest tests.test_browser_server
Ran 40 tests in 7.145s
OK

npm run docs:build
build complete in 2.03s

npm test
vitest: 7/7 passed
python unittest: Ran 418 tests in 205.403s
OK

bin/vidux help config && bin/vidux help signpost
PASS, help lists config path|check|show|init and signpost emit|summary|trace.
```

## Files In This Slice

- `bin/vidux`
- `scripts/vidux-config.py`
- `scripts/vidux-doctor-cli.sh`
- `scripts/vidux-completion.sh`
- `scripts/vidux_signpost.py`
- `tests/test_vidux_config_cli.py`
- `tests/test_signpost.py`
- `tests/test_browser_server.py`
- `package.json`
- `README.md`
- `docs/reference/config.md`
- `docs/reference/commands.md`
- `docs/reference/hooks.md`
- `docs/reference/scripts.md`
- `investigations/2026-06-03-vidux-five-hour-observability-future-plan.md`

## Non-Claims

- No live `vidux.config.json` was created in the repo.
- No external board, GitHub mutation, PR, push, or commit was performed.
- No real Claude or Cursor process was launched; the trace smoke uses local env attribution and a temp JSONL log.
- No live Voxtral/MLX read-aloud server was started; browser evidence is static/server contract coverage.
- The larger five-hour objective remains active; this completes only 5.3.0da, the first slice of the 10-task plan.
