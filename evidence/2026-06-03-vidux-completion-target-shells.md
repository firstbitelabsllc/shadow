# Vidux Completion Target Shells Smoke

Date: 2026-06-03
Task: 5.3.0ep Completion target-shell parity

## Finding

`vidux completion <shell>` expects one of `bash`, `zsh`, or `fish`, but the
generated bash and zsh completion scripts treated `completion` like `help` and
suggested Vidux subcommands instead of target shell names. Fish already
suggested the target shells.

## Change

- Split bash `help` and `completion` branches.
- Bash now suggests `bash zsh fish --help -h` for `vidux completion`.
- Zsh now suggests `bash`, `zsh`, and `fish` shell targets for
  `vidux completion`, plus help flags.
- Fish now also exposes `--help` / `-h` under `vidux completion`.
- Added a contract test that rejects the old `help|completion)` shared branch
  and checks rendered bash/zsh/fish output.

## Proof

```text
bash -n scripts/vidux-completion.sh bin/vidux
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_completion_command_completes_shell_targets
PASS (1 test)

bash scripts/vidux-completion.sh bash | rg -n 'bash zsh fish|help\|completion|completion\)'
PASS; bash completion branch renders target shells.

bash scripts/vidux-completion.sh zsh | rg -n "completion\)|Emit bash completion|Emit zsh completion|Emit fish completion|help\|completion"
PASS; zsh completion branch renders target shells.

bash scripts/vidux-completion.sh fish | rg -n "__fish_seen_subcommand_from completion|bash zsh fish|-l help"
PASS; fish renders target shells and help flag.

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_status_help_matches_current_scan_scope tests.test_vidux_contracts.ViduxContractTests.test_vidux_completion_command_completes_shell_targets
PASS (2 tests)

npm run docs:build
PASS; vitepress build completed in 1.89s.

git diff --check -- scripts/vidux-completion.sh tests/test_vidux_contracts.py
PASS

python3 scripts/vidux-publish-scrutiny.py --json ... --task 5.3.0ep
PASS; ready=true.

rg -n "evt_codex_20260603_5e30ep_completion_target_shells" ~/.agent-ledger/activity.jsonl
PASS; ledger row at /Users/leokwan/.agent-ledger/activity.jsonl:5920.
```

## Non-Claims

- No `vidux completion` runtime behavior changed.
- No install scripts or shell rc files were modified.
- No full packaged `npm test` rerun after this narrow slice yet.
- No local-CI lane, external mutation, stage, commit, push, or PR.
