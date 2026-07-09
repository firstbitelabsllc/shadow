# Vidux doctor install CLI contract hardening

Date: 2026-06-03
Task: 5.3.0dw Doctor install CLI contract hardening
Lane: vidux-five-hour-observability

## Bug

`vidux doctor --bogus` correctly exited with code 2, but the install doctor
script help documented only exit codes 0 and 1. The terminal help also said the
footer was always `N/7`, even though the script computes the denominator from
the checks it actually ran.

There was also no hermetic contract test for the skip-npm install doctor path.
The existing live smoke depends on Leo's actual machine auth/config, which is
useful evidence but not a stable regression fixture.

## Change

Updated:

- `scripts/vidux-doctor-cli.sh`
- `bin/vidux`
- `docs/reference/scripts.md`
- `docs/reference/commands.md`
- `tests/test_vidux_contracts.py`
- `PLAN.md`

The install doctor now documents invalid usage as exit code 2, the top-level
help says the footer prints an `N/TOTAL` summary, and the docs reference names
the same exit-code contract. Added a machine-independent skip-npm fixture that
stubs `gh`, uses a temporary `HOME`, points `VIDUX_ROOT` at a temporary config
checker, and proves the doctor path without running real `npm test`.

## Gates

- `bash -n bin/vidux scripts/vidux-doctor-cli.sh` PASS.
- Focused doctor contract tests PASS, 2/2:
  - `test_doctor_split_is_documented_for_cli_and_runtime_hooks`
  - `test_install_doctor_skip_npm_fixture_is_machine_independent`
- Focused doctor/docs contract tests PASS, 3/3.
- `bin/vidux help doctor | rg '2 for invalid usage|N/TOTAL summary|install/readiness doctor|scripts/vidux-doctor.sh --json'` PASS.
- `bin/vidux doctor --bogus` PASS with `rc=2`, `unknown flag`, and help text
  containing `2   invalid usage, such as an unknown flag`.
- `VIDUX_DOCTOR_SKIP_NPM_TEST=1 bin/vidux doctor` PASS, 7/7.
- `npm run docs:build` PASS.
- `git diff --check -- PLAN.md bin/vidux docs/reference/commands.md docs/reference/scripts.md scripts/vidux-doctor-cli.sh tests/test_vidux_contracts.py` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dw_doctor_cli_contract` verified at
  `~/.agent-ledger/activity.jsonl:5810`.

## Non-claims

- No runtime doctor behavior, runtime `--fix`, config mutation, token-file
  mutation, npm-test full gate, product app, local-CI lane, external service,
  stage, commit, push, or PR mutation was performed.
