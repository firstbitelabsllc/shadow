# PLAN.md Field Reference

Fields scaffolded by `vidux init --here`. For the discipline and cycle, see
[Five Principles](/concepts/principles), [The Cycle](/concepts/cycle), and
[PLAN.md Structure](/concepts/plan-structure).

## Section Order

The scaffold uses this order:

| # | Section | Required | Purpose |
|---|---|:---:|---|
| 1 | `# <Project Name>` | ✔ | Title — one H1, matches the project |
| 2 | `## Purpose` | ✔ | One paragraph. User-visible goal. |
| 3 | `## Evidence` | ✔ | Cited facts the plan is built on |
| 4 | `## Constraints` | ✔ | ALWAYS / NEVER rules |
| 5 | `## Operator Brief` | ✔ | Current status, outcome, next move, and validation |
| 6 | `## Outcome Scorecard` | ✔ | Baseline, target, current result, and proof |
| 7 | `## Tasks` | ✔ | Ordered task queue with status tags |
| 8 | `## Decision Log` | ✔ | Intentional choices future readers must preserve |
| 9 | `## Progress` | ✔ | Results, uncertainty, and cold-resume state |

### Canonical Outcome fields

An owning plan may opt into the provider-neutral `vidux.outcome.v1` source by
adding these rows to its existing `Operator Brief`:

```markdown
- Outcome ID: checkout-notes
- Outcome Revision: 7
- Outcome Updated At: 2026-08-02T04:45:22Z
- Outcome State: working
```

The existing `Outcome` and `Next` rows supply the summary and current move.
The revision is explicit and must increase whenever this semantic Outcome
changes; it must never be derived from file time, path, task counts, or a
provider receipt. Vidux projects only these allowlisted fields into one
`vidux.outcome.v1` document. It does not copy the plan body, paths, sessions,
prompts, provider metadata, or raw text. A plan without all four canonical
rows remains a legacy dashboard brief and is not treated as a typed Outcome.

## Task Status FSM

```
  pending ─────▶ in_progress ─────▶ completed
                      │
                      └── blocked
```

| Status | Meaning | Who sets it |
|---|---|---|
| `[pending]` | Queued, not yet started | Plan owner |
| `[in_progress]` | The row to resume first | Current owner |
| `[completed]` | Requested outcome exists and named gate passed | Current owner |
| `[blocked]` | Cannot proceed; reason and resume condition recorded | Current owner |

Repository-specific hosts may project review state separately. The portable
plan contract uses the four states above.

**Rules:**

- Resume `[in_progress]` before selecting another row.
- The default cycle advances one bounded row, checkpoints, then exits.
- `[completed]` is earned by inspectable proof, never assertion.
- `[blocked]` names the exact condition that would make the row runnable again.

## Task Annotations

Inline markers are optional and should stay readable:
`- [pending] T-7: update install docs [Depends: T-3] [Evidence: README.md]`.

| Annotation | Purpose | Example |
|---|---|---|
| `[Evidence: ...]` | Cited source backing this task | `[Evidence: src/auth.ts:42 — no idempotency key]` |
| `[Depends: T-N]` | Blocks until the named row is `[completed]` | `[Depends: T-3]` |
| `[Investigation: path]` | Compound task — read sub-plan before coding | `[Investigation: investigations/payment-flow.md]` |
| `[Blocker: ...]` | What's blocking, on `[blocked]` tasks | `[Blocker: needs production analytics credentials]` |
| `[Drift: ...]` | Drift Log entry that explains why a stale task was blocked or replaced | `[Drift: D-20260522-01]` |
| `[Fix: file:line]` | Where the fix landed, on `[completed]` tasks | `[Fix: src/auth.ts:42]` |
| `[Shipped: <sha>]` | Commit sha the fix landed in | `[Shipped: a1b2c3d]` |

## Decision Log Entry Types

The Decision Log records choices a cold reader might otherwise undo or repeat.
Use a bracketed type and date when a decision needs a stable identifier:
`[TAG] [YYYY-MM-DD]`.

| Type | When to use | Template |
|---|---|---|
| `[DELETION]` | Removed something deliberately — future agents must not re-add it | `[DELETION] [2026-04-16] Removed X-endpoint. Reason: deprecated by Y. Do not re-add.` |
| `[DIRECTION]` | Chose approach X over Y for a stated reason | `[DIRECTION] [2026-04-16] Chose an idempotency key. Reason: it fits the existing request boundary.` |
| `[SCOPE]` | Cut scope — what's in, what's explicitly out | `[SCOPE] [2026-04-16] Email notifications deferred to v2. Reason: requires SES provisioning.` |
| `[PIVOT]` | Course correction — old direction obsolete, new direction active | `[PIVOT] [2026-04-16] Was targeting Postgres; now targeting Cloudflare D1. Reason: edge-compatible.` |
| `[CONSTRAINT]` | Discovered a hard constraint | `[CONSTRAINT] [2026-04-16] Requests must remain idempotent. Reason: clients retry.` |
| `[REVERSAL]` | Undoing a prior Decision Log entry — reference the old one | `[REVERSAL] [2026-04-16] Revert [DIRECTION 2026-03-12]. Reason: the named gate regressed.` |

Tags make later inspection deterministic; they do not trigger automation.

## Progress Entry Format

One line per meaningful cycle. The Progress line orients the next reader to the
result, proof, remaining uncertainty, and one next move.

```
- [YYYY-MM-DD] Outcome and proof. Risk: remaining uncertainty. Next: one move.
```

**Do:**
- Open with a verb (shipped, investigated, blocked, promoted, archived)
- Reference stable row ids: `completed T-7`
- Cite files when the reader needs them: `see fix at src/auth.ts:42`

**Don't:**
- Treat the diff or git log as the whole handoff — cite the row, proof, and resume point
- Write "everything fine" lines — nothing to report, no entry
- Paraphrase the plan — reference it by row id

### Optional checkpoint helper

`vidux checkpoint` requires `--proof` for completion and a concrete `--blocker`
for blocked work. It edits the matching task and Progress entry but leaves those
changes uncommitted unless `--commit` is supplied. A configured local ledger may
receive a projection; local `done` maps to `needs_review`, not an open pull
request or shipped state.

## Drift Entry Format

When implementation materially diverges from the plan, an optional
`## Drift Log` entry can preserve why:

```
- [YYYY-MM-DD] D-YYYYMMDD-NN — T-N
  - Planned: ...
  - Actual: ...
  - Why: ...
  - Plan update: ...
  - Next: ...
```

This is repository prose, not an automation trigger. Update affected task rows
explicitly.

## Evidence Source Tags

Use inspectable, public-safe sources:

| Tag | Points to |
|---|---|
| `[Source: codebase grep]` | A grep hit in the repo, format `file:line pattern` |
| `[Source: revision]` | A Git revision and relevant path |
| `[Source: test]` | A command and bounded result |
| `[Source: observed]` | A directly observed behavior or reproduction |
| `[Source: artifact]` | A repository-local screenshot, report, or receipt |

Keep credentials, private account data, personal paths, raw chats, and runtime
identifiers out of public plans.

## Constraints Block Format

Two subsections — what must be true, what is forbidden.

```markdown
## Constraints
- ALWAYS: integration tests hit the real database (no mocks)
- ALWAYS: run lint + build before commit
- NEVER: edit content/posts/**/*.mdx body text
- NEVER: skip pre-commit hooks
```

**Rule of thumb:** constraints survive the project. A rule that applies to one task goes on the task line, not in Constraints.

## Compound Task Sub-Plan Structure

A task with `[Investigation: investigations/<slug>.md]` has a sub-plan in this structure:

```markdown
# Investigation: <surface name>

## Reporter Says
<exact quote from feedback / ticket>

## Evidence
<files, related tickets, recent commits, repro steps>

## Root Cause
<the specific code path — not symptoms>

## Impact Map
<other UI paths / tickets / state flows affected>

## Fix Spec
<file:line changes with evidence for why>

## Tests
<assertions covering this ticket AND related tickets>

## Gate
<build passes, tests pass, visual check (for UI)>
```

Use the investigation only while it reduces genuine uncertainty. The owning row
completes when its requested outcome exists and named gate passes.

## See Also

- [Five Principles](/concepts/principles) — the doctrine behind the queue
- [The Cycle](/concepts/cycle) — how a plan gets executed each run
- [PLAN.md Structure](/concepts/plan-structure) — template shape and section order
