# Vidux Config CLI Smoke

Date: 2026-06-03
Task: 5.3.0fd Config CLI terminal smoke

## Scope

Smoked the user-facing `vidux config` CLI without creating or mutating a live
`vidux.config.json`.

## Proof

```text
bin/vidux config path
PASS; /Users/leokwan/Development/vidux/vidux.config.example.json

bin/vidux config show --json
PASS; status=ok, source=example, using_example=true,
live_config_present=false, plan_store.path_exists=true,
inbox_sources_enabled=1, token_file redacted and path_exists=true.

bin/vidux config check --json
PASS; status=ok with no issues and the checked paths:
vidux.config.json, vidux.config.example.json.

bin/vidux config check --strict --json
PASS expected failure; exit=1, status=fail, issue code=live_config_missing.

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0fd ...
PASS; ready=true with invariant, regression, and adversarial review passes.

/Users/leokwan/Development/ai/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30fd_config_cli_smoke ...
PASS; verified in /Users/leokwan/.agent-ledger/activity.jsonl at line 6029.
```

## Non-Claims

- No live `vidux.config.json` was created.
- No config `init` command was run.
- No token or secret value was printed.
- No external adapter sync was run.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.
