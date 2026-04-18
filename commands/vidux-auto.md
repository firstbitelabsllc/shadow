---
name: vidux-auto
description: "DEPRECATED (2026-04-17): merged into /vidux Part 2. Use /vidux for both discipline and automation. This command file is a migration breadcrumb and will be removed 2026-07-17."
---

# /vidux-auto (DEPRECATED)

This command has been merged into `/vidux` as **Part 2: Automation**. Use `/vidux` for both discipline and automation work — it now contains:

- **Part 1: Discipline** — five principles, cycle, PLAN.md template, investigations
- **Part 2: Automation** — 24/7 fleet model, lane management, subagent delegation (research + implementation dispatch), lane bootstrap recipe — lives in [guides/automation.md](../guides/automation.md) as opt-in, NOT inline in SKILL.md
- **`references/automation.md`** — full doctrine (session-gc internals, Codex shim gotchas, PR lifecycle nursing, cross-fleet coordination), read on demand from inside a `/vidux` session

## Why this changed

`/vidux` is the single entry point now. Part 1 (discipline) lives in SKILL.md; Part 2 (automation) lives in `guides/automation.md` as an opt-in companion. Users shouldn't have to pick between `/vidux` and `/vidux-auto` at invocation time — the split was a historical artifact from when automation patterns were bolted on incrementally.

## What to do

- If you see a lane prompt that says `Load: /vidux, /vidux-auto` — update it to `Load: /vidux`. `/vidux` now has Part 2 inline.
- If you need the full automation reference (session-gc internals, Codex shim gotchas, PR lifecycle nursing, cross-fleet coordination), see `references/automation.md` in this repo.

## Migration breadcrumb

- **Merged:** 2026-04-17
- **Removal target:** 2026-07-17 (90-day breadcrumb window)
- **Superseded by:** `/vidux` Part 2 + `references/automation.md`

## Related deprecations (removed in the same pass)

- `/vidux-claude` — platform-specific Claude automation; patterns now live in `/vidux` Part 2
- `/vidux-codex` — Codex delegation companion; patterns now live in `/vidux` Part 2 (research + implementation dispatch) and the shim registration recipe in `references/automation.md`
- `/vidux-fleet`, `/vidux-dashboard`, `/vidux-manager`, `/vidux-plan` — pruned as orphaned companions with zero active references
