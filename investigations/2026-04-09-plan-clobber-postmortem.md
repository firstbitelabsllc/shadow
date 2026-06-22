# Postmortem: PLAN.md Merge Clobber in strongyes-web

**Date:** 2026-04-09 · **Severity:** High · **Detection:** Manual · **TTR:** Hours (manual)

## What happened

Merge commit `b95d2839` resolved a PLAN.md conflict in favor of the stale branch `codex/t74-prep-mobile-honesty` (created pre-Phase-12), deleting ~20 tasks (T81-T92, Phases 12-13). The result was still valid Markdown that parsed cleanly in `vidux-loop.sh` — a *silent* state regression. Both `strongyes-backend` and `strongyes-release-train` then hit `auto_pause_recommended` because their queued/in-progress tasks no longer existed. User detected it hours later and restored PLAN.md manually.

## Root cause

PLAN.md is the single source of truth for the fleet (Doctrine 1: "Plan is the store") but had no merge protection — git treated it like any code file. A code clobber fails the build and is caught instantly; a PLAN.md clobber just yields fewer tasks, and nothing detected that tasks *disappeared*.

Contributing:
- **Long-lived plan-carrying branch.** The branch predated two phases of additions and carried its own PLAN.md edit, forcing a conflict on merge days later. No rebase discipline required branches to pick up main's PLAN.md additions.
- **Conflict resolved to branch version wholesale** — no content-aware merge, no `.gitattributes` rule.
- **No pre/post-merge validation and no alerting on task-count drops.** `vidux-loop.sh` counts tasks only at read time; "all tasks done" and "all tasks deleted" both look like zero pending.

## Durable lesson

PLAN.md needs database-level protection: never let a merge silently reduce its contents. Long-lived branches are plan time bombs — every automation that adds tasks in the interim becomes a victim of the eventual merge. `auto_pause_recommended` masks this: the park signal needs a "why" (queue drained normally vs. plan shrank unexpectedly).

## Fixes (decisions)

- **R1 — `.gitattributes` `PLAN.md merge=union`** (P0): append-only safety net. Keeps both sides on conflict; duplicates are detectable/fixable, deleted tasks are not.
- **R2 — Task-count sidecar `.plan-taskcount`** (P0): updated on every checkpoint in `vidux-checkpoint.sh`; `vidux-loop.sh` fleet-health compares current count against it. Drop > threshold (3) with no `[DELETION]` Decision Log entry ⇒ `PLAN_INTEGRITY_WARNING` + `auto_pause`.
- **R3 — Pre/post-merge snapshot** (P1): `_plan_snapshot` before merge-back, `_plan_verify` after; abort if pending+in_progress drops > threshold.
- **R4 — Worktree Handoff Protocol rule** (P1): *PLAN.md is main-authoritative.* On merge-back, take main's PLAN.md (`git checkout main -- PLAN.md`), then re-apply only the branch's own task-status change as a separate commit. Branches older than 24h MUST rebase onto main first. Never accept a branch's full PLAN.md over main's; if in doubt, abort and escalate.
- **R5** (P2): custom `plan-safe` merge driver for projects with >5 automations — evaluate only if `merge=union` proves insufficient (keep the fix bounded, Doctrine 12).
