# Vidux Fish Help Completion Smoke

Date: 2026-06-03
Task: 5.3.0er Fish help-completion parity

## Finding

Fish top-level completion advertised the `help` subcommand, but
`vidux help <tab>` omitted `help` from the target list. Bash and zsh use the
canonical subcommand list and already included it.

## Change

- Added `help` to the fish `__fish_seen_subcommand_from help` target list.
- Added a contract test so fish help-target completion stays aligned with the
  canonical Vidux subcommands.

## Proof

```text
bash -n scripts/vidux-completion.sh bin/vidux
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_fish_help_completion_includes_help_subcommand
PASS (1 test)

bash scripts/vidux-completion.sh fish | rg -n "__fish_seen_subcommand_from help.*completion help"
PASS

npm run docs:build
PASS; vitepress build completed in 1.89s.

git diff --check -- scripts/vidux-completion.sh tests/test_vidux_contracts.py
PASS

python3 scripts/vidux-publish-scrutiny.py --json ... --task 5.3.0er
PASS; ready=true.

rg -n "evt_codex_20260603_5e30er_fish_help_completion" ~/.agent-ledger/activity.jsonl
PASS; ledger row at ~/.agent-ledger/activity.jsonl:5938.
```

## Non-Claims

- No runtime behavior changed.
- No bash or zsh completion output changed for this slice.
- No full packaged `npm test` rerun after this narrow slice yet.
- No shell rc/install mutation.
- No local-CI lane, external mutation, stage, commit, push, or PR.
