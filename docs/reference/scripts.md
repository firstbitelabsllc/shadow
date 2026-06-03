# Scripts Reference

The `scripts/` directory contains the executable support layer for vidux. Most files are shell or Python utilities with clear responsibilities documented in their header comments.

## Core cycle and plan scripts

| Script | Purpose |
|---|---|
| `scripts/vidux-loop.sh` | Read-only stateless cycle helper that reads a plan and emits machine-readable next-action state, including raw `hot_tasks`, blocker- and stuck-aware `runnable_tasks`, `refresh_proof` routing, stuck-loop `surface_switch` candidates that skip mechanically stuck rows plus explicit blocker, dependency-gated, section-completion-gated, and owner/operator approval-gated rows, `handoff_contract` fields on selected-task, missing-plan, and no-task early-exit paths, latest observed stale-proof dates, meter checkpoints, required `task_id` / resume metadata, and archive-pressure warnings. Default read mode does not rewrite the plan or append loop-start ledger rows unless explicitly opted in; explicit `--checkpoint` records the plan/progress mutation without inventing commit proof. |
| `scripts/vidux-checkpoint.sh` | Structured checkpoint helper for marking work done, blocked, or archived. Its checkpoint ledger row carries the derived plan task id, plan path, proof, handoff status, files claimed, and next-agent resume. Its two entry shapes are `vidux-checkpoint.sh <plan> <task> <summary> ...` and `vidux-checkpoint.sh <plan> --archive`. |
| `scripts/vidux-drift-log.py` | Records planned-vs-actual implementation drift in `## Drift Log`, appends Progress, writes optional prevention-hint cache rows, emits optional signposts, and can explicitly block stale tasks, add follow-up tasks, or mirror the drift into named subplans. Exposed as `vidux drift`. |
| `scripts/vidux-config.py` | User-facing config inspector and initializer. Resolves `vidux.config.json`, falls back to `vidux.config.example.json`, validates plan-store, external-root, inbox-source, and token-file shape, warns on obvious inline secrets, expands configured paths, and prints redacted summaries. Exposed as `vidux config`. |
| `scripts/vidux_signpost.py` | Emits, wraps, summarizes, traces, lifecycle-smokes, and spawned-subagent-smokes local JSONL signposts for helper actions such as `drift.record`, `hook.beforeTask`, `subagent.spawn`, `task.verify`, and `hook.afterTask`. Exposed as `vidux signpost`. |
| `scripts/vidux-status.py` | Read-only status board for operational `PLAN.md` files under the configured roots. Default output hides only empty or fully shipped plans, skips example/fixture trees, prefers task-level `Claims board` status tables over stale task stubs, and keeps plans with literal or prose-blocked rows visible with blocker counts. |
| `scripts/vidux-plan-gc.py` | Mechanical plan garbage collection for completed tasks, old investigations, and oversized inboxes. |
| `scripts/vidux-plan-bank-audit.py` | Read-only audit for plan-bank closure drift. It scans one or more repo roots for `PLAN.md` files, skips `.claude`/`.agents`/`.codex` plan mirrors by default unless `--include-agent-mirrors` is set, reports missing Progress/Evidence/Constraints/Decision Log/Drift Log/Closeout sections, archived non-terminal rows, blocked rows without `blocked_since`, unchecked gate checkboxes, and `/tmp/` proof references, can repeat with watch iterations for multi-hour observe-only smoke runs, can write each iteration to an explicit JSONL output artifact with `--output-jsonl`, and can summarize that artifact with root-by-root breakdowns via `--summarize-jsonl`. |
| `scripts/vidux-plan-gc-cron.sh` | Scheduled wrapper around `vidux-plan-gc.py`. |
| `scripts/vidux-inbox-sync.py` | Round-trip sync between `PLAN.md` task state and external kanban adapters; `PLAN.md` remains the queue/planning authority and publish ledger rows carry shipped-cycle proof/resume. |
| `scripts/vidux-pr-body.py` | Builds the canonical ready-PR body with lane, existing plan path/checkbox-FSM task row, concise summary, proof, matching publish ledger eid that exists as a publish event in the hot/archive ledger for the same lane/task/summary/plan/proof/handoff/changed-files/file-claims/resume packet, claimed files that resolve to existing paths or git-known deletions, self-scrutiny review-pass, resume, and change fields. |
| `scripts/vidux-publish-scrutiny.py` | Read-only preflight for publish packets. It fails closed unless summary/existing plan path/checkbox-FSM task row/proof/publish ledger eid/handoff/path-like file and claim/resume metadata exists, claims include every file-claimed entry, claimed paths resolve to existing paths or git-known deletions, and invariant, regression, and adversarial review passes are recorded as passing. |
| `scripts/vidux-release.sh` | Plan/ledger-gated release helper. In `--apply` mode, release publish requires an existing plan path/task row, proof, handoff status, changed-file claims, and next-agent resume before VERSION/CHANGELOG/PLAN/git/ledger mutations; default VERSION/CHANGELOG/PLAN files and extra `--file` entries are claimed automatically. |
| `scripts/vidux-claims.py` | Append-only claims bus for claiming, releasing, and listing active repo surfaces in `~/.agent-ledger/claims.jsonl`. |

## Checkpoint script contract

The checked-in hook manifest points at `scripts/vidux-checkpoint.sh`, but the raw script is not a bare post-task hook:

- Normal checkpoint mode: `vidux-checkpoint.sh <plan-path> <task-description> <summary> [--blocker <text>] [--status done|done_with_concerns|blocked] [--outcome useful|busy|blocked_clarified]`
- Archive mode: `vidux-checkpoint.sh <plan-path> --archive`

If you wire it into an app-level `afterTask` event, wrap it with the task-specific arguments you want to record; the normal checkpoint path derives `task_id` from the task row prefix.

## Health and verification scripts

| Script | Purpose |
|---|---|
| `scripts/vidux-doctor-cli.sh` | User-facing install/readiness doctor exposed as `vidux doctor`. Checks python, GitHub CLI auth, token permissions, `~/Development`, stale browser pidfiles, config validity, and the contract test bundle unless skipped. |
| `scripts/vidux-doctor.sh` | Runtime health checks for plans, worktrees, automations, browser processes, and Codex state. |
| `scripts/vidux-http-smoke.py` | Observe-only HTTP smoke helper for local monitor budgets. It classifies fast responses as `pass`, responses that stream bytes before timing out as `warn_partial`, and zero-byte budget timeouts as `fail_budget`, while keeping only a bounded response sample so app-route probes do not dump full HTML or huge JSON into evidence. JSON `ok` follows hard-fail exit status; `strict_ok` is false when any warning is present. `--timeout` must be greater than 0, and `--max-sample-bytes` must be 0 or greater. |
| `scripts/vidux-test-all.sh` | Comprehensive self-test harness for contract tests and related checks. |
| `scripts/vidux-fleet-quality.sh` | Classifies automation runs into quick, deep, mid, and normal quality buckets. |
| `scripts/vidux-firstbite-observe.py` | Observe-only FirstBite local-CI report reader that ranks red/stale lane observations, emits `vidux-drift-log.py` commands, and suppresses dispatch even when `BRAIN_AUTODISPATCH` is truthy. Duplicate lint requires the same lane and meaningful run id so older lane drift cannot hide fresh red proof. |
| `scripts/vidux-firstbite-diagnose.py` | Read-only FirstBite failed-execute diagnoser. It reads `report.json` plus referenced `run.log` files, strips terminal color, clusters repeated failure signatures, and can write JSON/Markdown resume packets without rerunning local-CI lanes or dispatching workers. |
| `scripts/vidux-worktree-gc.py` | Read-only by default. Classifies worktrees into `primary`, `open_pr`, `merged_clean`, `dirty`, `closed_unmerged`, `unmerged_no_pr`, and `unknown`, emits a top-level `cleanup_decision` with `guarded_removal_available`, `owner_approval_required_before_apply`, and `cleanup_approval_status`, emits `owner_review_items` with `commits_not_in_base`, `last_commit_subject`, `last_commit_date`, `last_commit_age_days`, and safe `review_command` inspection commands, emits `safe_cleanup_items` for exact `merged_clean` rows with `cleanup_approval_status=required_before_apply`, and can print a Markdown owner-review packet with non-removable review rows plus safe cleanup row evidence via `--owner-review-markdown`; with owner approval, `--apply --yes` removes only `merged_clean` worktrees and protects both the primary checkout and the invocation checkout from removal. |

### Doctor split

Use `vidux doctor` when a human or terminal lane needs local CLI readiness:
python version, GitHub auth, token permissions, local config, stale browser
pidfile state, and the contract bundle. It may run `npm test`, so use
`VIDUX_DOCTOR_SKIP_NPM_TEST=1` only in fast loops that already have a separate
test gate. The install doctor exits `0` when all checks pass, `1` when any
check fails, and `2` for invalid usage.

Use `scripts/vidux-doctor.sh --json` when a hook or monitor needs runtime
health: plans, worktrees, automations, browser processes, and Codex state. This
runtime doctor is read-only by default and JSON-friendly, so it is the
beforeTask/pre-hook probe. `scripts/vidux-doctor.sh --fix` is an explicit
cleanup path and should not be wired into automatic pre-hook checks. Orphan
automation cleanup stays `warn` when safety rules retain a directory instead of
deleting it.

The runtime doctor keeps macOS memory fields source-specific: the thresholded
percentage is reported from `memory_pressure -Q` as
`memory_pressure_free_pct`, while raw page-derived MB values from `vm_stat` are
reported as `vm_free_mb` and `vm_speculative_mb`. Legacy aliases remain in JSON
for existing consumers.

## Codex maintenance scripts

| Script | Purpose |
|---|---|
| `scripts/codex-gc.sh` | Garbage-collect Codex caches, sessions, and archived rollout data. |
| `scripts/codex-gc-cron.sh` | Scheduled wrapper around `codex-gc.sh` with timestamped logging. |
| `scripts/vidux-fleet-rebuild.sh` | Manual Codex fleet rebuild utility that stops processes and rewrites automation DB state. |

## Support libraries in `scripts/lib/`

| Library | Purpose |
|---|---|
| `codex-db.sh` | Safe Codex database read/write helpers. |
| `compat.sh` | Portable wrappers for OS-specific `stat` and `date` behavior. |
| `ledger-config.sh` | Ledger path discovery from env vars and config. |
| `ledger-emit.sh` | Emit vidux events into the shared ledger. |
| `ledger-query.sh` | Fleet analysis queries over ledger data. |
| `queue-jsonl.sh` | Experimental derived JSONL queue helpers alongside `PLAN.md`; `PLAN.md` remains the queue/planning authority and publish ledger rows carry shipped-cycle proof/resume. |
| `resolve-plan-store.sh` | Resolve the configured plan store path. |

## How to navigate the directory

- Start with the header comment in each script. The repo is disciplined about stating purpose and usage at the top of the file.
- `scripts/vidux-worktree-gc.py` is covered by `tests/test_worktree_gc.py`, and CI runs that suite in the dedicated `worktree-gc-tests` job.
- Use [Configuration](/reference/config) when a script reads defaults from `vidux.config.json`.
- Use [Hooks](/reference/hooks) if you want lightweight git-based enforcement instead of a full automation lane.
