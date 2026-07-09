# Vidux runtime doctor orphan-fix false-green hardening

Date: 2026-06-03
Task: 5.3.0eh Runtime doctor orphan-fix false-green hardening
Lane: vidux-five-hour-observability

## Finding

The runtime doctor orphan automation cleanup could report `status=pass` and
`fixed=true` for `--fix` whenever orphan automation directories existed, even
if safety rules retained one because its `memory.md` was longer than the
deletion threshold.

On this machine, the live read-only warning currently lists two orphan
automation directories:

- `codex-plans-auditor` has a one-line `memory.md`.
- `strongyes-10m-cleanup` has an eight-line `memory.md`.

That shape would have made live `--fix` partial, so a full pass/fixed claim
would be misleading.

## Changes

- `scripts/vidux-doctor.sh` now tracks removed and retained orphan automation
  directories separately.
- In `--fix` mode, the orphan check returns `warn`, `fixed=false`,
  `fixed_count`, `retained_count`, retained `details`, and `removed` names when
  any directory is retained by the safety threshold.
- When all orphan directories are removed, the check returns `pass`,
  `count=0`, `fixed=true`, `fixed_count`, `retained_count=0`, and `removed`.
- `docs/reference/scripts.md` now says orphan cleanup can remain `warn` when
  safety rules retain a directory.
- `tests/test_vidux_contracts.py` adds a hermetic fixture with one removable
  orphan and one retained orphan.

## Verification

```text
bash -n scripts/vidux-doctor.sh
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_doctor_orphan_fix_does_not_false_green_retained_dirs
Ran 1 test in 0.933s
OK

python3 -m unittest <nearby runtime doctor contract slice>
Ran 10 tests in 20.302s
OK

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_doctor_split_is_documented_for_cli_and_runtime_hooks tests.test_vidux_contracts.ViduxContractTests.test_install_doctor_skip_npm_fixture_is_machine_independent
Ran 2 tests in 0.351s
OK

scripts/vidux-doctor.sh --json
WARN 11/14 with orphan automation, stale in-progress, and bimodal-runtime warnings preserved

npm run docs:build
PASS

git diff --check -- PLAN.md scripts/vidux-doctor.sh tests/test_vidux_contracts.py docs/reference/scripts.md evidence/2026-06-03-vidux-playwright-e2e-smoke.md
PASS
```

- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30eh_runtime_doctor_orphan_fix` verified at `~/.agent-ledger/activity.jsonl:5869`.

## Non-claims

- This did not run live `scripts/vidux-doctor.sh --fix`.
- This did not clean up live automation directories, stale project rows,
  bimodal-runtime warnings, product repos, or local-CI execute lanes.
- No stage, commit, push, PR, or external mutation was performed.
