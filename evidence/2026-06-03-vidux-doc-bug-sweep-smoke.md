# Vidux documentation bug sweep smoke - 2026-06-03

## Scope

Task: `5.3.0dh Documentation bug sweep`.

Goal: fix source-drift in current config, commands, hooks/scripts, browser, and setup docs found during the five-hour Vidux observability pass.

## Drift receipts

- `commands/vidux.md` still described "The plan is truth", `commit cleanly`, and a raw commit checkpoint shape instead of the owning plan plus publish-ledger packet.
- `docs/reference/commands.md` still summarized startup as reading `vidux.config.json` without the current `vidux config check --json` and example-fallback distinction.
- `SETUP_NEW_MACHINE.md` compaction reminders still pointed at repo-local `.agent-ledger/activity.jsonl` instead of the centralized `~/.agent-ledger/activity.jsonl` plus repo-local companion-state caveat, and still told operators not to use the Codex desktop app for Vidux work.
- `docs/reference/browser.md` omitted shipped browser routes for `/receipts`, receipt upload/list/image/tag/OCR/expected/delete/analyze, and read-aloud reference-audio upload.
- `scripts/vidux-checkpoint.sh` parsed `--outcome`, but its usage text omitted the flag.

## Files changed

- `commands/vidux.md`
- `docs/reference/commands.md`
- `SETUP_NEW_MACHINE.md`
- `docs/reference/browser.md`
- `scripts/vidux-checkpoint.sh`
- `tests/test_vidux_contracts.py`
- `PLAN.md`

## Proof

- Receipt grep PASS over patched surfaces for `vidux config check --json`, centralized ledger path, browser receipt routes, `/api/upload-ref-audio`, and checkpoint `--outcome`.
- Stale-phrase check PASS: removed the old command/setup/checkpoint strings listed in drift receipts.
- `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_docs_bug_sweep_matches_current_command_setup_browser_surfaces tests.test_vidux_contracts.ViduxContractTests.test_fleet_lifecycle_docs_share_config_doctor_signpost_contract tests.test_vidux_contracts.ViduxContractTests.test_doctor_split_is_documented_for_cli_and_runtime_hooks` PASS, 3/3.
- `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_core_checkpoint_breadcrumbs_require_plan_then_ledger_then_git tests.test_vidux_contracts.ViduxContractTests.test_loop_and_guide_scope_plan_authority_and_publish_ledger_truth tests.test_vidux_contracts.ViduxContractTests.test_hooks_scripts_exist` PASS, 3/3.
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests.test_readaloud_storybook_decision_does_not_add_browser_build_stack tests.test_browser_server.BrowserViduxTruthTests` PASS, 3/3.
- `bash -n scripts/vidux-checkpoint.sh` PASS.
- `npm run docs:build` PASS, VitePress build complete.
- `git diff --check -- commands/vidux.md docs/reference/commands.md SETUP_NEW_MACHINE.md docs/reference/browser.md scripts/vidux-checkpoint.sh tests/test_vidux_contracts.py PLAN.md evidence/2026-06-03-vidux-doc-bug-sweep-smoke.md` PASS.
- Publish ledger `evt_codex_20260603_5e30dh_docs_bug_sweep` verified in `/Users/leokwan/.agent-ledger/activity.jsonl:5793`.
- `python3 scripts/vidux-publish-scrutiny.py --json ... --ledger evt_codex_20260603_5e30dh_docs_bug_sweep ...` PASS with `ready=true`.

## Proof hygiene note

One initial receipt-grep attempt used double quotes around Markdown backticks and triggered shell expansion (`PLAN.md: command not found`). No files changed. The grep was rerun with single quotes and passed cleanly.

## Non-claims

- No browser runtime behavior or route implementation changed.
- No hook install, hook runner, app repair, live config mutation, local-CI execute, external mutation, stage, commit, push, PR, or upstream merge happened.
- The larger five-hour objective remains active after this row.
