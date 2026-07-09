# Vidux Fish Config And Signpost Completion Smoke

Date: 2026-06-03
Task: 5.3.0et Fish config/signpost completion parity

## Finding

Fish completion only suggested `vidux config` and `vidux signpost`
subcommands. It did not expose the config flags that bash/zsh already expose
(`--json`, `--strict`, `--config`, `--source`, etc.) or the signpost flags
needed for call-stack proof (`--run-id`, `--runtime`, `--log`, etc.).

## Change

- Added fish completion entries for `vidux config` options:
  `--config`, `--json`, `--strict`, `--path`, `--source`, `--force`, `--help`.
- Added fish completion entries for `vidux signpost` options:
  `--feature`, `--action`, `--status`, `--duration-ms`, `--exit-code`,
  `--called`, `--emitter`, `--meta`, `--log`, `--run-id`, `--runtime`,
  `--limit`, `--json`, `--help`.
- Added a contract test so fish config/signpost option completion cannot
  regress to subcommands-only.

## Proof

```text
bash -n scripts/vidux-completion.sh bin/vidux
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_fish_config_and_signpost_options_match_user_cli
PASS (1 test)

bash scripts/vidux-completion.sh fish | rg -n "__fish_seen_subcommand_from config.*-l (config|json|strict|path|source|force|help)"
PASS

bash scripts/vidux-completion.sh fish | rg -n "__fish_seen_subcommand_from signpost.*-l (feature|action|status|duration-ms|exit-code|called|emitter|meta|log|run-id|runtime|limit|json|help)"
PASS

npm run docs:build
PASS; vitepress build completed in 1.89s.

git diff --check -- scripts/vidux-completion.sh tests/test_vidux_contracts.py
PASS

bin/vidux config check --json
PASS; status=ok, source=example, live_config_present=false, using_example=true.

bin/vidux signpost summary --json
PASS; total_events=20 before the lifecycle smoke, with hook/subagent/task features present.

bin/vidux signpost lifecycle-smoke --json
PASS; emitted ordered Codex beforeTask, Claude subagent spawn, Cursor verify,
and Codex afterTask events under one run id.

bin/vidux status --root ~/Development/vidux --focus vidux
PASS; root vidux row rendered at 98% with [3p/1b].

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0et ...
PASS; ready=true with invariant, regression, and adversarial review passes.

~/<private-skill-root>/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30et_fish_config_signpost_completion ...
PASS; verified in ~/.agent-ledger/activity.jsonl at line 5955.
```

## Non-Claims

- No config runtime behavior changed.
- No signpost runtime behavior changed.
- No shell rc/install files were modified.
- No full packaged `npm test` rerun after this narrow slice yet.
- No runtime-doctor warning cleanup, local-CI lane, external mutation, stage,
  commit, push, or PR.
