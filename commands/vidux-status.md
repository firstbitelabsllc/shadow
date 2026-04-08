---
name: vidux-status
description: Quick status check. Shows task state, recent progress, and blockers from the authority PLAN in a one-screen summary.
---

# /vidux-status

Quick, read-only status check. Does not modify any files.

## Steps

1. Read `vidux.config.json` and resolve the authority `PLAN.md`.

2. If no PLAN.md exists, report:
   ```
   No PLAN.md found on this branch. Run /vidux or /vidux-plan to start.
   ```

3. If PLAN.md exists, produce a one-screen summary:

### Task Progress

Count completed and total tasks from the Tasks section.
Treat `- [x]` as completed and `- [ ]` as pending for older plans.

```
Tasks: 7/15 complete (47%)
[=========>           ]
```

Show:
- the current `[in_progress]` task, if any
- the next 3 actionable `[pending]` tasks
- any `[blocked]` tasks with their blocker text

### Context Budget

Report hot (non-completed) and cold (completed) task counts.
If cold tasks > 30 or total lines > 200, note: "Context budget warning — consider running vidux-checkpoint.sh --archive"

### Recent Progress

Show the last 5 entries from the Progress section (most recent first).

### Blockers

Show unresolved Q-refs that block the next actionable task.
Show any `[blocked]` tasks.
Show the latest unresolved Surprise, if one exists.
If no blockers, say "No blockers."

### Decision Log

Report whether a Decision Log exists and how many tagged entries it contains.

### Current Phase

Determine and report the current phase:
- **EXECUTE** if a task is `[in_progress]`.
- **GATHER** if the next task lacks evidence.
- **PLAN** if the next task is blocked by task-linked open questions.
- **VERIFY** if all tasks are done but final verification is pending.
- **COMPLETE** if all tasks are complete and verified.

## Hard Rules

- Read only. Do not modify PLAN.md or any other file.
- Keep the output to one screen (roughly 30-40 lines).
- No commentary or suggestions. Just the facts.
