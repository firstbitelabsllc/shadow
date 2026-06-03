# Vidux Status Completion Options Smoke

Date: 2026-06-03
Task: 5.3.0en Status option completion parity

## Finding

`vidux help status` and `/vidux-status` documented `--root`, `--focus`, `--all`,
and `--json`, but the generated shell completion scripts only completed the
`status` subcommand name. After choosing `vidux status`, bash fell back to
`--help -h`, and zsh/fish had no status-specific options.

## Change

- Added `status` option completions to `scripts/vidux-completion.sh` for bash.
- Added a zsh `status)` branch for `--root`, `--focus`, `--all`, `--json`,
  `--help`, and `-h`.
- Added fish `__fish_seen_subcommand_from status` completions for the same
  user-facing options.
- Extended the status help/spec contract so rendered bash/zsh/fish completion
  output must include the documented status flags.

## Proof

```text
bash -n scripts/vidux-completion.sh bin/vidux
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_status_help_matches_current_scan_scope
PASS (1 test)

bash scripts/vidux-completion.sh bash | rg -n -- '--root|--focus|--all|--json'
PASS; status branch renders --root --focus --all --json.

bash scripts/vidux-completion.sh zsh | rg -n -- '--root|--focus|--all|--json'
PASS; status branch renders --root, --focus, --all, --json descriptions.

bash scripts/vidux-completion.sh fish | rg -n -- '-l root|-l focus|-l all|-l json'
PASS; fish renders status long-option completions.

npm run docs:build
PASS; vitepress build completed in 1.87s.

git diff --check -- scripts/vidux-completion.sh tests/test_vidux_contracts.py
PASS

python3 scripts/vidux-publish-scrutiny.py --json ... --task 5.3.0en
PASS; ready=true.

rg -n "evt_codex_20260603_5e30en_status_completion_options" ~/.agent-ledger/activity.jsonl
PASS; ledger row at /Users/leokwan/.agent-ledger/activity.jsonl:5902.
```

## Non-Claims

- No `vidux status` runtime behavior changed.
- No browser status UI changed.
- No JSON schema changed.
- No full packaged `npm test` rerun after this completion-options slice yet.
- No local-CI lane, external mutation, stage, commit, push, or PR.
