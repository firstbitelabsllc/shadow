# Board write atomicity proof — 2026-08-28

Scope: `scripts/shadow_root_board.py` and `tests/test_root_board.py` only, on top of current `origin/main` `4b268497` (which already carries merged PRs #540 and #541).

## Defect

Every root-board mutation wrote `board.json` and committed the journal in two
separate steps. A catchable failure between the steps (for example a rejected
journal commit) left the new board bytes behind while journal HEAD stayed at
the prior commit: the operation reported failure but the authority had already
escaped. A failed `shadow claim` could leave a ghost claim owned by no
accepted operation.

## Red control

`tests.test_root_board.AWriteCountsWithNoRemoteConfigured.test_claim_journal_failure_restores_board_and_head_exactly`
injects a journal failure into `shadow claim`. Against pre-repair source the
test failed: `board.json` retained the injected `failed-seat` claim while
journal HEAD stayed at the prior commit (2026-08-28T05:13:41Z).

## Green repair

All catchable split `_write()` + `_commit()` mutation paths now route through
the existing `_write_and_commit()` transaction owner: claim, release,
reserve-completion, reconcile, set-priority, migrate-to-local-plan, and
discard-unclaimed-source-alias. Recovery no longer uses `git reset --hard`;
it restores the journal with a verified `update-ref` guarded by
`_is_expected_board_commit` (parent, single-board-file diff, published bytes,
and subject must match exactly), refuses to roll back a journal that changed
outside the transaction, restores the index only when the board file was
staged, and re-verifies head + bytes + porcelain status before surfacing the
original failure. `_initialize_git` now refuses an existing `index.lock`
instead of silently deleting it.

## Mutation kill

An in-memory mutation restoring the split `_write()` then `_commit()` sequence
makes the regression fail again on changed board bytes, so the test kills the
escaped defect rather than passing vacuously (2026-08-28T05:23:14Z).

## Gates on the exact candidate

- Focused root-board suite: 106/106 OK (149.9s), plus two earlier OK runs.
- Full suite `shadow-ci.py run --run-all true`: 1179 tests OK (1051.6s, 3 skipped — the same skips as CI).
- Release gauntlet `shadow-ci.py gauntlet`: all 7 stages OK — story e2e x2,
  migration/lifecycle (171 tests), adversarial/crash, capability/rotation,
  rollback/upgrade, release-package-and-install; package smoke OK
  (1.3.0, 115 files, sha256=89ca4f7fe1bb8570c09981c224857d6525fc52e45d40376175af9212ef133c6b).
- Installed `shadow doctor`: post-merge install receipt tracked by the owning plan.

## Environment flake found and fixed in the same lane

`test_restart_resumes_owned_row_and_two_seats_take_disjoint_rows` erred
intermittently (~1/3) on this machine: `TemporaryDirectory` cleanup raced a
pex bootstrap cache written into the fixture HOME after the test's last
assertion. Root cause: the test's `zsh -lc` login shell rebuilds PATH via
`/usr/libexec/path_helper`, which orders `/usr/local/bin` ahead of
`/opt/homebrew/bin`; a machine-local git shim installed there spawns an
asynchronous pex-based analytics uploader on every git invocation, and the
uploader's first-run bootstrap lands in `$HOME/Library/Caches/pex` seconds
after the test's last command exits. CI never sees this (no such shim). Fix:
the test module pins `PEX_ROOT` to a module-lived directory outside every
fixture, so background shims and fixtures never share a directory. Verified:
6/6 consecutive runs of the formerly flaky test pass and no pex cache appears
inside any fixture home; the pin is environment-generic and names no vendor.

## Groundtruth gap

The red control uses an injected journal failure, not a physical crash
mid-fsync; crash-atomicity of the filesystem itself is out of scope. The
first full-suite run of this branch erred once with the shim race above
before the PEX_ROOT pin; all receipts after the pin are flake-free. A failed
transaction that cannot even restore the journal (for example a destroyed
`.git`) still surfaces `root board journal failed and exact recovery also
failed` by design.
