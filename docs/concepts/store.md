# Repository Authority

Vidux authority lives in repository files and Git. The owning `PLAN.md` records
the outcome, queue, decisions, progress, proof references, and one next move.
Linked evidence carries details that would make the plan hard to scan.

## Why Repository Files?

Sessions and workers change. A repository path and revision are inspectable by
the current maintainer and the next reader without trusting chat history,
provider state, or a hidden service.

## The Durable Locations

```
vidux-project/
├── PLAN.md                    ← queue/planning authority
├── evidence/
│   └── result.md              ← optional linked proof
└── investigations/
    └── slug.md                ← optional linked investigation
```

`INBOX.md` or another repo-native intake file may be used when the project
already has one. Vidux does not require it.

### PLAN.md

One owning plan per outcome. Reuse an existing plan when it already owns the
work instead of creating a competing queue.

`vidux init --here` scaffolds eight sections:

| Section | Purpose |
|---|---|
| Purpose | User-visible outcome |
| Evidence | Facts that shape the work |
| Constraints | Boundaries that must survive handoff |
| Operator Brief | Current status, outcome, next move, and validation |
| Outcome Scorecard | Baseline, target, current result, and proof |
| Tasks | Ordered rows with explicit state |
| Decision Log | Choices a future reader must preserve or revisit deliberately |
| Progress | Results, uncertainty, and cold-resume state |

See [PLAN.md Structure](/concepts/plan-structure) for the full template.

### Linked evidence

Put large test output, screenshots, investigations, or decision detail in
repository files and link them from the active row. Git preserves revision
history; Vidux does not require a particular evidence directory or filename.

### investigations/

Sub-plans for complex bugs or surfaces needing root cause analysis before code. Every investigation follows the seven-section template:

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

Use this shape when root cause is genuinely uncertain. Small, obvious repairs
do not need an investigation document.

### Git History

Git supplies revision and diff identity. A commit or pull request is not proof
that the requested outcome exists; the plan should point to the test, artifact,
or observation that proves it.

## Optional Local Ledger

`vidux checkpoint` edits the matching task and Progress entry, requires explicit
proof for completion, and leaves plan changes uncommitted by default. `--commit`
is opt-in.

When a local ledger is configured, the helper may append a row for local
inspection. Local `done` maps to `needs_review`, not an open pull request or
shipped state.

Repository files and Git remain sufficient authority. A ledger row is not a
publication gate and grants no push, merge, release, deploy, or external-send
authority.
