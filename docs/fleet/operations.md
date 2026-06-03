# Fleet Operations

This page summarizes the repo's operational guidance from `guides/automation.md` and `guides/fleet-ops.md`. It is for running a multi-lane vidux setup after the core planning discipline is already in place.

## Operating model

The automation guide keeps one invariant front and center: lanes persist on disk, while sessions are disposable.

- Durable files live in the lane directory and the project plan store.
- Session logs are hot state and are expected to cycle or be garbage-collected.
- The guide calls out `session-gc` as mandatory for 24/7 fleets so session logs do not grow without bound.

## Lane management

The repo's default pattern is one coordinator lane per active repo, not a large swarm of specialists.

- One coordinator reduces plan stampedes.
- The same lane that ships a change is expected to fix the fallout from that change.
- The current guidance is 2-4 total lanes for 1-3 active repos, with a hard cap of 6 lanes per session.
- The "polish-brake" rule forces a surface switch if the last three checkpoints all ship from the same area.

## Dispatch model

The automation guide splits subagent work into two shapes:

- `Research dispatch` reads a large surface and compresses it to a short summary with evidence lines.
- `Implementation dispatch` edits files from a five-block spec and leaves the parent to review the diff.

The decision tree is simple:

- Read-heavy work goes to research dispatch.
- Clear, bounded code-writing work goes to implementation dispatch.
- Small, obvious changes stay in the parent lane.

## Lifecycle observability

Every dispatch cycle should leave the same local proof shape, regardless of
whether the parent runtime is Claude Code, Codex, or an editor-bound Cursor
lane:

- `vidux config check --json` proves the local config or example fallback before plan-store assumptions.
- `scripts/vidux-doctor.sh --json` is the beforeTask runtime health probe; `vidux doctor` remains the terminal install/readiness doctor.
- One `VIDUX_SIGNPOST_RUN_ID` ties together `hook.beforeTask`, `subagent.spawn`, `task.verify`, and `hook.afterTask`.
- `VIDUX_RUNTIME=claude`, `VIDUX_RUNTIME=codex`, or `VIDUX_RUNTIME=cursor` keeps spawned worker attribution honest.
- `vidux signpost trace --run-id <id>` is the ordered call-stack receipt; `vidux signpost lifecycle-smoke --json` is the disposable trace-shape smoke; `vidux signpost spawned-subagent-smoke --json` is the disposable inherited-env attribution smoke.
- The final handoff is still the owning `PLAN.md` plus matching publish ledger row, not the signpost log alone.

## Coordination checks

The fleet operations guide makes several checks mandatory before a lane acts:

- Read recent sibling `memory.md` entries.
- Check hot files before touching a surface another lane may already own.
- Verify trunk health early so a dirty or diverged main checkout does not waste a long cycle.
- Reuse or merge existing worktrees instead of silently spawning new ones.

## Writer and scanner gates

The fleet guide distinguishes two gate families:

- `Quick check` gates are for writers and plan-driven workers.
- `SCAN` gates are for radars and scanners that inspect the codebase itself.

A writer on the wrong plan may waste a cycle. A scanner on the wrong gate can stay dead forever, because it exits on plan state instead of scanning the owned surface.

## Worktree and branch discipline

The fleet guide treats PR sweep and worktree handoff as operational requirements:

- The owning `PLAN.md` plus matching publish ledger row is the durable shipped-work recovery packet; open automation PRs are transport/review handles and should be swept before new branch work starts.
- Active worktrees should be resumed or garbage-collected instead of duplicated.
- `vidux-worktree-gc.py` protects both the primary checkout and the checkout it is invoked from; only `merged_clean` rows are auto-removable.
- PLAN changes should stay append-mostly so stale merges do not clobber task queues.
- Lanes should not exit with unexplained local worktree commits or branch-only drift.

## Inbox and merge conflict protocol

`guides/fleet-ops.md` also documents:

- An `INBOX.md` handoff pattern for radar-to-writer promotions.
- Merge conflict rules for plan files and long-lived worktrees.
- A fleet-health coordinator pattern for detecting dead lanes, collisions, and repeated blockers.

## Recommended companions

- Read [Recipe Catalog](/fleet/recipes) for reusable patterns such as PR review, deploy watching, and retry-with-backoff.
- Read [Harness Authoring](/fleet/harness) before changing a lane prompt.
- Read [Configuration](/reference/config) if you need the repo-level defaults that these scripts and guides rely on.
