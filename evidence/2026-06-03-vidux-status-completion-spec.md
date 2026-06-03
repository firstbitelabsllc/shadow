# Vidux status completion and command spec convergence

Date: 2026-06-03
Task: 5.3.0el Status completion/spec scope convergence
Lane: vidux-five-hour-observability

## Finding

After the status help scope fix, shell completions and the `/vidux-status`
command spec still carried older status-board assumptions:

- Completion descriptions said status printed active-plan status across
  `projects/*/PLAN.md`.
- `commands/vidux-status.md` listed a narrow `~/Development/vidux/projects/*`
  shape, still said blocked rows were excluded from progress denominator, and
  said there were no other arguments.

## Changes

- zsh and fish completion descriptions now match top-level `vidux help`:
  "Print plan status across operational PLAN.md files."
- `/vidux-status` now describes operational `PLAN.md` scanning under a selected
  root, current `vidux status --root/--focus/--all/--json` usage, default hiding
  of empty/shipped plans, and blocked-inclusive progress percentage.
- `tests/test_vidux_contracts.py` now guards top help, status help, completions,
  and the command spec against the stale `projects/*/PLAN.md` framing.

## Verification

```text
bash -n scripts/vidux-completion.sh bin/vidux
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_status_help_matches_current_scan_scope
Ran 1 test in 0.036s
OK

bash scripts/vidux-completion.sh zsh | rg -n "status:|projects/\\*/PLAN|operational PLAN"
9:    'status:Print plan status across operational PLAN.md files'

bash scripts/vidux-completion.sh fish | rg -n "status|projects/\\*/PLAN|operational PLAN"
14:complete -c vidux -n '__vidux_no_subcommand' -a status     -d 'Print plan status across operational PLAN.md files'

npm run docs:build
PASS

rg -n "Print active-plan status across projects/\\*/PLAN\\.md|~/Development/vidux/projects/\\*/PLAN\\.md|No other arguments" commands/vidux-status.md scripts/vidux-completion.sh bin/vidux tests/test_vidux_contracts.py docs/reference/commands.md
PASS with only negative assertion hits
```

- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30el_status_completion_spec` verified at
  `/Users/leokwan/.agent-ledger/activity.jsonl:5885`.

## Non-claims

- This did not change status runtime behavior, browser plan-discovery globs,
  status JSON schema, local-CI execute lanes, external services, stage, commit,
  push, or PR.
- The packaged `npm test` gate was not rerun after this row.
