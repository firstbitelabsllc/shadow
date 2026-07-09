# Vidux HTTP smoke README and completion contract

Date: 2026-06-03
Task: 5.3.0dn HTTP smoke README and completion contract
Lane: vidux-five-hour-observability

## Change

Made the bounded HTTP monitor helper discoverable from the top-level README and
guarded shell completion output against drift.

Updated:

- `README.md` status/config commands, helper prose, and scripts inventory.
- `tests/test_http_smoke.py` completion-output contract for bash, zsh, and fish.
- `tests/test_vidux_contracts.py` README drift guard.
- `PLAN.md` Phase 5.4 row.

## Gates

- `python3 -m py_compile scripts/vidux-http-smoke.py tests/test_http_smoke.py tests/test_vidux_contracts.py` PASS.
- `bash -n bin/vidux scripts/vidux-completion.sh` PASS.
- `python3 -m unittest tests.test_http_smoke tests.test_vidux_contracts.ViduxContractTests.test_docs_bug_sweep_matches_current_command_setup_browser_surfaces` PASS, 8/8.
- `npm run docs:build` PASS.
- `git diff --check -- README.md PLAN.md tests/test_http_smoke.py tests/test_vidux_contracts.py evidence/2026-06-03-vidux-http-smoke-readme-completion.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dn_http_smoke_readme_completion` verified at `~/.agent-ledger/activity.jsonl:5801`.

## Live Completion Smoke

Command:

```bash
for shell in bash zsh fish; do
  bin/vidux completion "$shell" | rg 'http-smoke|--max-sample-bytes|--timeout|--url'
done
```

Result: PASS. Bash, zsh, and fish completion output all include `http-smoke`
plus `--url`, `--timeout`, `--max-sample-bytes`, and `--json`.

## Non-claims

- No HTTP helper behavior changed.
- No Litty or Moussey route was repaired.
- No app backend, LaunchAgent, local-CI lane, external service, stage, commit,
  push, or PR mutation was performed.
