# Vidux HTTP smoke CLI

Date: 2026-06-03
Task: 5.3.0dm HTTP smoke CLI discoverability
Lane: vidux-five-hour-observability

## Change

Exposed `scripts/vidux-http-smoke.py` through the user-facing CLI as `vidux http-smoke`.

Updated:

- `bin/vidux` top-level help, subcommand help, and dispatcher.
- `scripts/vidux-completion.sh` bash, zsh, and fish completions.
- `docs/reference/commands.md` shell CLI note.
- `tests/test_http_smoke.py` dispatch/help coverage.
- `tests/test_vidux_contracts.py` command-reference drift guard.

## Gates

- `bash -n bin/vidux scripts/vidux-completion.sh` PASS.
- `python3 -m py_compile tests/test_http_smoke.py tests/test_vidux_contracts.py` PASS.
- `python3 -m unittest tests.test_http_smoke tests.test_vidux_contracts.ViduxContractTests.test_docs_bug_sweep_matches_current_command_setup_browser_surfaces` PASS, 7/7.
- `npm run docs:build` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dm_http_smoke_cli` verified at `~/.agent-ledger/activity.jsonl:5800`.

## Live CLI Smoke

Command:

```bash
bin/vidux http-smoke --json --timeout 3 --max-sample-bytes 80 \
  http://127.0.0.1:4321/api/health \
  http://127.0.0.1:4400/workers
```

Result: PASS for CLI dispatch and warning semantics.

| URL | Verdict | Duration | Bytes |
|---|---:|---:|---:|
| `http://127.0.0.1:4321/api/health` | pass | 10ms | 309 |
| `http://127.0.0.1:4400/workers` | warn_partial | 3003ms | 73728 |

The command exited 0 because warning-only partial responses are not treated as hard failures.

## Non-claims

- No HTTP helper behavior changed beyond CLI dispatch.
- No Litty or Moussey route was repaired.
- No app backend, LaunchAgent, local-CI lane, external service, stage, commit, push, or PR mutation was performed.
