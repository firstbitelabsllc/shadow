---
name: vidux-auto
description: "DEPRECATED (2026-04-17): merged into /vidux Part 2. Use /vidux for both discipline and automation. This command file is a migration breadcrumb and will be removed 2026-07-17."
---

# /vidux-auto (DEPRECATED)

This command has been merged into `/vidux` as **Part 2: Automation**. Use `/vidux` for both discipline and automation work — it now contains:

- **Part 1: Discipline** — five principles, cycle, PLAN.md template, investigations
- **Part 2: Automation** — 24/7 fleet model, lane management, delegation modes (Mode A + Mode B), lane bootstrap recipe
- **`references/automation.md`** — full doctrine (session-gc internals, Codex shim gotchas, PR lifecycle nursing, cross-fleet coordination), read on demand from inside a `/vidux` session

## Why this changed

Users shouldn't have to pick between `/vidux` (discipline) and `/vidux-auto` (automation) at invocation time. The split was a historical artifact from when automation patterns were bolted on incrementally. The single-entry-point model means:

- User asks: *"run this every hour"* → `/vidux` activates and uses Part 2 lane bootstrap recipe
- User asks: *"what's the plan for feature X"* → `/vidux` activates and uses Part 1 cycle/template
- User never types `/vidux-auto`

## What to do

- If you see a lane prompt that says `Load: /vidux, /vidux-auto` — update it to `Load: /vidux`. `/vidux` now has Part 2 inline.
- If you need the full automation reference (session-gc internals, Codex shim gotchas, PR lifecycle nursing, cross-fleet coordination), see `references/automation.md` in this repo.

## Migration breadcrumb

- **Merged:** 2026-04-17
- **Removal target:** 2026-07-17 (90-day breadcrumb window)
- **Superseded by:** `/vidux` Part 2 + `references/automation.md`

## Related deprecations (removed in the same pass)

- `/vidux-claude` — platform-specific Claude automation; patterns now live in `/vidux` Part 2
- `/vidux-codex` — Codex delegation companion; patterns now live in `/vidux` Part 2 (Mode A + Mode B) and the shim registration recipe in `references/automation.md`
- `/vidux-fleet`, `/vidux-dashboard`, `/vidux-manager`, `/vidux-plan` — pruned as orphaned companions with zero active references
