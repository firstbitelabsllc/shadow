# The Store

The Store is the persistence layer. Every fact Vidux needs to survive an interrupted session lives in one of four locations — PLAN.md, `evidence/`, `investigations/`, or git history. No databases. No daemons. No in-memory state.

## Why Files?

AI agents are stateless. Authentication expires. Sessions crash. The only state that reliably survives a dead session is a file committed to git.

The Store is designed around one constraint: **any agent, resuming cold, must reach full context within 90 seconds of reading the Store.**

## The Four Locations

```
vidux-project/
├── PLAN.md                    ← source of truth
├── INBOX.md                   ← unprocessed findings
├── evidence/
│   └── YYYY-MM-DD-slug.md     ← research snapshots
└── investigations/
    └── slug.md                ← root cause analysis + fix specs
```

### PLAN.md

One per project. The single source of truth for what needs to happen, what has been decided, and what actually happened.

Eight required sections — missing any produces known failure modes:

| Section | What happens without it |
|---|---|
| Purpose | Agents optimize for the wrong goal |
| Evidence | Tasks are guesses; wrong fixes get shipped |
| Constraints | Agents violate hard requirements |
| Tasks | No queue — agents improvise unpredictably |
| Decision Log | Agents re-add deleted code or undo deliberate pivots |
| Open Questions | Unknowns stay invisible until they cause failures |
| Surprises | Unexpected findings get lost |
| Progress | No history — agents can't tell what actually happened |

See [PLAN.md Structure](/concepts/plan-structure) for the full template.

### evidence/

Evidence snapshots back the decisions in PLAN.md. Named `YYYY-MM-DD-<slug>.md` so they stay sorted and interpretable after time passes.

Write an evidence snapshot when:
- A grep or audit produces findings that inform a task
- An external API response, PR comment, or design doc needs to be cited
- A Decision Log entry references a data point that might disappear

Evidence files are **append-only**. Update by adding a new dated file, never by editing an old one. The old file is the record of what was believed at a point in time.

### investigations/

Sub-plans for complex bugs or surfaces that need root cause analysis before code. Every investigation follows the seven-section template:

```markdown
# Investigation: [surface name]

## Reporter Says        — exact quote from feedback
## Evidence             — files, related tickets, recent commits, repro steps
## Root Cause           — the specific code path, not symptoms
## Impact Map           — other UI paths, other tickets, state flow
## Fix Spec             — file:line changes with evidence for why
## Tests                — assertions covering this ticket and related tickets
## Gate                 — build passes, tests pass, visual check (for UI)
```

**No Fix Spec = no code.** The investigation is the work until the Fix Spec section is filled.

Investigations are **durable**. They stay in `investigations/` after the parent task completes. Future agents who touch the same surface read them before acting.

### Git History

Git is the timeline. Every checkpoint commit records what changed and why, in a format any agent can parse:

```
vidux: add rate limiting to login endpoint
```

The commit message is the single source of truth for what happened in a cycle. The Progress log in PLAN.md mirrors it — if they diverge, the git log wins.

## INBOX.md

`INBOX.md` is the drop zone for unprocessed findings from humans, external tools, or scanners.

Rules:
- Agents check `INBOX.md` during READ, before looking at tasks
- Promote actionable findings to `[pending]` tasks in PLAN.md
- Annotate non-actionable ones with `[SKIP: reason]`
- Maximum 20 entries — if full, archive oldest to `evidence/`

## The Invariant

> **State lives in files, never in memory.**

If it's not in the Store, it doesn't exist. Summaries in chat history, notes in agent memory, to-do lists in scratch pads — all of these die when the session ends. Only the Store survives.
