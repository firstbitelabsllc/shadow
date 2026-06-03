# Vidux Runtime Doctor Memory Label Smoke

Date: 2026-06-03
Task: 5.3.0ev Runtime doctor memory label honesty

## Finding

`scripts/vidux-doctor.sh --json` reported `memory_free_pct` next to
`free_mb` and `speculative_mb`, but those values come from different macOS
commands. The percentage is parsed from `memory_pressure -Q`; the MB values are
page counters derived from `vm_stat`. The old names made the live JSON look
internally inconsistent even when the runtime check was healthy.

## Change

- Added source-specific JSON fields:
  `memory_pressure_free_pct`, `memory_pct_source`, `vm_free_mb`,
  `vm_speculative_mb`, and `vm_pages_source`.
- Preserved legacy aliases: `memory_free_pct`, `free_mb`, and
  `speculative_mb`.
- Updated human runtime doctor output to say `System memory_pressure free`.
- Updated config/scripts reference docs so the threshold source is explicit.
- Added a contract test that keeps the source-specific fields and aliases
  present.

## Proof

```text
bash -n scripts/vidux-doctor.sh
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_runtime_doctor_memory_fields_name_their_sources tests.test_vidux_contracts.ViduxContractTests.test_doctor_json_output_is_valid tests.test_vidux_contracts.ViduxContractTests.test_doctor_checks_have_required_fields
PASS (3 tests)

scripts/vidux-doctor.sh --json | python3 -c '...project system_memory_pressure...'
PASS; live output includes memory_pressure_free_pct=64, memory_pct_source="memory_pressure -Q",
vm_free_mb=91.0, vm_speculative_mb=41.5, vm_pages_source="vm_stat", and legacy aliases.

scripts/vidux-doctor.sh | rg -n "System memory_pressure free|System memory pressure unavailable|!|BLOCK|ok"
PASS; human output renders "System memory_pressure free: 64% (min: 15%)".

npm run docs:build
PASS; vitepress build completed in 1.92s.

git diff --check -- scripts/vidux-doctor.sh tests/test_vidux_contracts.py docs/reference/config.md docs/reference/scripts.md
PASS

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0ev ...
PASS; ready=true with invariant, regression, and adversarial review passes.

/Users/leokwan/Development/ai/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30ev_runtime_doctor_memory_labels ...
PASS; verified in /Users/leokwan/.agent-ledger/activity.jsonl at line 5973.
```

## Non-Claims

- No runtime-doctor warning cleanup was attempted.
- No `scripts/vidux-doctor.sh --fix` was run.
- No memory threshold changed.
- No full packaged `npm test` rerun after this narrow slice yet.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.
