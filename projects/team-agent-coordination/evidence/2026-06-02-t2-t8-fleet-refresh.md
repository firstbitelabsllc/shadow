# T2/T8 Fleet Refresh - 2026-06-02

Scope: read the latest fleet-cleanup dry-run output, repair only the missing
`linear-health-watch` LaunchAgent surface from its maintained source, and leave
T8 cleanup as read-only because no Resplit deletion bucket is approved.

No worktrees, branches, caches, logs, Linear issues, human messages, or Resplit
code were deleted or mutated by this review. The only live mutation was
reinstalling the `com.leokwan.linear-health-watch` LaunchAgent from the
maintained `ai-leo` script so the existing :15/:45 cron reference is true again.

## Inputs

- `fleet-cleanup --dry-run`, cycle timestamp `2026-06-02T01:30:51Z`
- `~/bin/linear-health-watch --status`
- `launchctl print gui/$(id -u)/com.leokwan.linear-health-watch`
- `plutil -p ~/Library/LaunchAgents/com.leokwan.linear-health-watch.plist`
- `bash /Users/leokwan/Development/ai-leo/skills/linear-health-watch/scripts/run-once.sh --dry-run`
- `bash /Users/leokwan/Development/ai-leo/skills/linear-health-watch/scripts/run-once.sh --install`

## Fleet-Cleanup Dry-Run

Disk remains pressured but not critically low:

- `/System/Volumes/Data`: `95%` used, `52Gi` available
- `/`: `25%` used, `52Gi` available

Eligible safe-cache actions in dry-run:

- Xcode DerivedData older than 24h: none
- `/tmp/resplit-dd-*` older than 6h: none
- npm cache clean: safe regenerable cache, size not probed

T8 read-only inventory:

- Xcode DerivedData: `0B`, reclaimable candidate `0.0MiB`
- `/private/tmp/resplit-dd-*`: `1` dir, reclaimable candidate `0.0MiB`
- Tuist caches/runs: `80K`, `80K`, and `614M`
- Resplit top-level sibling dirs: `4`, about `10209.8MiB`
- Oversized ledger logs: none

Resplit worktree cleanup remains blocked by ownership state:

- `vidux`: `removable=0`, `dirty=1`, `unmerged_no_pr=2`
- `resplit-ios`: `removable=0`, `open_pr=4`, `unmerged_no_pr=3`
- `resplit-web`: `removable=0`, `dirty=3`, `closed_unmerged=1`, `unmerged_no_pr=4`

Non-claim: `strongyes-web` reports `removable=17`, but that is outside this
Resplit T8 cleanup slice and was not touched.

## Lane-Staleness Finding

`fleet-cleanup --dry-run` reported:

- `resplit-watch`: OK, `LaunchAgent=loaded`
- `resplit-2-0-loop`: OK, `LaunchAgent=loaded`
- `linear-health-watch`: DEAD, `LaunchAgent=enabled-not-loaded`
- `strongyes-watch`: DEAD, `LaunchAgent=not-installed-or-not-loaded`

Direct verification found `~/bin/linear-health-watch` still pointed at an old
`.claude-snowcubes` source copy, `launchctl` could not find
`com.leokwan.linear-health-watch`, and
`~/Library/LaunchAgents/com.leokwan.linear-health-watch.plist` was missing.

## Linear-Health-Watch Repair

Pre-install dry-run from the maintained script passed without calling Claude:

- claims bus available at `/Users/leokwan/Development/ai/hooks/claims-bus.sh`
- reconcile dry-run `would-remove=0`
- inbox-sync dry-runs returned JSON with no errors

Then the maintained script was installed:

```bash
bash /Users/leokwan/Development/ai-leo/skills/linear-health-watch/scripts/run-once.sh --install
```

Post-install proof:

- `~/bin/linear-health-watch` now points at
  `/Users/leokwan/Development/ai-leo/skills/linear-health-watch/scripts/run-once.sh`
- plist `StartCalendarInterval` has minutes `15` and `45`
- `launchctl print gui/$(id -u)/com.leokwan.linear-health-watch` reports
  `state = not running`, `runs = 0`, and calendar triggers for minutes `15`
  and `45`

Non-claim: no post-repair scheduled `linear-health-watch` model cycle has fired
yet, and no sync-trio bootstrap was performed. LI-24 remains separate and
Leo-blocked per that lane's own memory.

## Perf-Sentinel

The dry-run also reported:

- memory headroom: `free=55%`, `swap=94%`
- `fseventsd`: about `16GB` RSS
- worktree feeders: `2823`

Per `/fleet-cleanup`, perf-sentinel is detect-only. No process was killed or
restarted. The practical next move is owner review/merge/archive of stale
worktrees plus a human reboot when convenient.

## Post-Refresh Resplit Status

While this proof was being finalized, the phase-shifted Resplit timers fired:

- `resplit-2-0-loop` cycle `1780363985` completed at `2026-06-02T01:35:12Z`
  with `LAST_VERDICT=QC-DEFERRED` and release row `clm_4133ae67e7e0`.
- `resplit-watch` cycle `1780364225` was active during verification, then
  completed at `2026-06-02T01:39:37Z` with wrapper `LAST_VERDICT=OK`,
  memory verdict `[SHIP] disk-thrash-recovery-watch-1-of-3`, and release row
  `clm_1a79e1957631`.

This does not close T2: the acceptance gate still requires a non-deferred
Resplit launch-loop state/ledger row, and the latest `resplit-2-0-loop` proof
is still deferred on the six-sub-pillar plus P4 dirty-tree gate.

## Resume

T2 remains open until a non-deferred Resplit launch-loop state/ledger row
exists. T8 remains open until an owner decision or lifecycle classifier reports
an approved Resplit cleanup bucket. Next agent should not delete Resplit
worktrees from this evidence alone.
