# Vidux status --all tracked-count label

Date: 2026-06-03
Task: 5.3.0ei Status `--all` tracked-count label honesty
Lane: vidux-five-hour-observability

## Finding

`vidux status --all` includes shipped rows, but the rendered "Other tracked
plans" bucket still labeled the count as `active`. That made an all-rows view
overstate active work.

## Changes

- Default rendered status output still labels the filtered count as `active`.
- Rendered `--all` output now labels the count as `tracked`.
- A temp-plan regression covers one active plan plus one shipped plan and proves
  default output says `1 active` while `--all` says `2 tracked`.

## Verification

```text
python3 -m py_compile scripts/vidux-status.py
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_status_all_labels_tracked_not_active_count
Ran 1 test in 0.133s
OK

python3 -m unittest <nearby status contract slice>
Ran 6 tests in 0.548s
OK

bin/vidux status --root ~/Development/vidux --focus vidux
Other tracked plans  (45 active)

bin/vidux status --root ~/Development/vidux --focus vidux --all
Other tracked plans  (67 tracked)

git diff --check -- scripts/vidux-status.py tests/test_vidux_contracts.py
PASS
```

- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30ei_status_all_label` verified at `~/.agent-ledger/activity.jsonl:5870`.

## Non-claims

- This did not change status sorting, JSON schema, status UI layout, or plan
  filtering.
- This did not clean up project plans, run local-CI execute lanes, stage,
  commit, push, PR, or mutate external services.
