# Vidux Browser Launcher Flags

Date: 2026-06-03
Task: 5.3.0fg Browser launcher flag parsing

## Finding

`bin/vidux-browse` silently ignored unknown arguments. A user-visible
`--port 7292` smoke still reused `http://127.0.0.1:7191`, and a nonsense flag
also exited 0 by reusing 7191. That made `vidux browse [args]` look configurable
while the launcher ignored the requested browser target.

## Change

- Added explicit launcher parsing for `--port`, `--host`, `--root`/`--dev-root`,
  `--open-host`, and `--comments-path`.
- Unknown flags and missing values now exit 2 with usage text.
- Foreground/background launches pass the parsed server args through to
  `browser/server.py`.
- Updated `vidux help browse`, `vidux-browse --help`, browser docs, and
  bash/zsh/fish completions for the actual launcher flags.

## Proof

```text
bash -n bin/vidux-browse bin/vidux scripts/vidux-completion.sh
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_browse_launcher_parses_flags_instead_of_silently_ignoring tests.test_vidux_contracts.ViduxContractTests.test_vidux_browse_help_and_completions_include_launcher_flags tests.test_vidux_contracts.ViduxContractTests.test_vidux_browse_launcher_reuses_only_matching_health
PASS; 3 tests.

bin/vidux-browse --definitely-not-a-real-flag --no-open
PASS expected failure; exit=2 with unknown-flag usage.

bin/vidux-browse --port
PASS expected failure; exit=2 with missing-value usage.

bin/vidux-browse --port 7292 --no-open
PASS; launcher targeted http://127.0.0.1:7292 instead of reusing 7191.
The temporary 7292 process was not retained after the smoke.

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_docs_bug_sweep_matches_current_command_setup_browser_surfaces tests.test_vidux_contracts.ViduxContractTests.test_vidux_browse_help_and_completions_include_launcher_flags tests.test_vidux_contracts.ViduxContractTests.test_vidux_completion_command_completes_shell_targets tests.test_vidux_contracts.ViduxContractTests.test_vidux_fish_help_completion_includes_help_subcommand
PASS; 4 tests.

npm run docs:build
PASS; VitePress build completed in 1.96s.

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0fg ...
PASS; ready=true with invariant, regression, and adversarial review passes.

/Users/leokwan/Development/ai/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30fg_browser_launcher_flags ...
PASS; verified in /Users/leokwan/.agent-ledger/activity.jsonl at line 6048.
```

## Non-Claims

- No Playwright e2e rerun after this launcher-flag slice.
- No full packaged `npm test` rerun after this launcher-flag slice yet.
- No persistent alternate-port browser process was left running.
- No runtime-doctor warning cleanup.
- No runtime doctor `--fix`.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.
