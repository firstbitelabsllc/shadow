# PLAN.md Field Reference

Quick reference for every section and annotation a vidux `PLAN.md` uses. For the discipline and cycle, see [SKILL.md](../../SKILL.md). For the full template, see [SKILL.md § PLAN.md Template](../../SKILL.md#planmd-template).

## Section Order

A canonical PLAN.md has these sections in this order. Sections marked *optional* may be omitted on small plans, but don't re-order the required ones — tooling and agent muscle memory expect them in sequence.

| # | Section | Required | Purpose |
|---|---|:---:|---|
| 1 | `# <Project Name>` | ✔ | Title — one H1, matches the project |
| 2 | `## Purpose` | ✔ | One paragraph. User-visible goal. |
| 3 | `## Evidence` | ✔ | Cited facts the plan is built on |
| 4 | `## Constraints` | ✔ | ALWAYS / NEVER rules |
| 5 | `## Tasks` | ✔ | Ordered task queue with status tags |
| 6 | `## Decision Log` | ✔ | Intentional choices future agents must not undo |
| 7 | `## Open Questions` | *optional* | Questions + research actions |
| 8 | `## Surprises` | *optional* | Unexpected findings, timestamped |
| 9 | `## Progress` | ✔ | Living per-cycle log |

## Task Status FSM

```
  pending ─────▶ in_progress ─────▶ completed
     ▲                │
     └── blocked ◀────┘
```

| Status | Meaning | Who sets it |
|---|---|---|
| `[pending]` | Queued with evidence, not yet started | Writer during plan authoring |
| `[in_progress]` | Actively being worked (one cycle or across cycles) | Any agent picking up the task |
| `[completed]` | Verified done: build ran, tests passed, visual check done | The agent that finished it |
| `[blocked]` | Can't proceed — needs a human unblock | Any agent that hits the block |

**Rules:**

- A task is `[in_progress]` for at most one cycle at a time. If the session dies mid-task, the next agent resumes it.
- A task appears in 3+ Progress entries while still `[in_progress]` → mark `[blocked]` with a Decision Log entry. Only a human unblocks it.
- `[completed]` is earned by verification evidence (a command, screenshot, or build output), not by assertion. Claiming complete without evidence is a lie (SKILL.md Principle 5).
- Status flows UP from sub-plans: an L1 task stays `[in_progress]` while its L2 investigation has any `(pending)` section.

## Task Annotations

Inline markers on a task line. Multiple can stack: `- [pending] Task 7: ship API docs [Depends: Task 3] [Evidence: Sentry def-123]`.

| Annotation | Purpose | Example |
|---|---|---|
| `[Evidence: ...]` | Cited source backing this task | `[Evidence: src/auth.ts:42 — no idempotency key]` |
| `[Depends: Task N]` | Blocks until task N is `[completed]` | `[Depends: Task 3]` |
| `[Investigation: path]` | Compound task — read sub-plan before coding | `[Investigation: investigations/payment-flow.md]` |
| `[Blocker: ...]` | What's blocking, on `[blocked]` tasks | `[Blocker: needs Leo's PostHog prod key]` |
| `[Fix: file:line]` | Where the fix landed, on `[completed]` tasks | `[Fix: src/auth.ts:42]` |
| `[Shipped: <sha>]` | Commit sha the fix landed in | `[Shipped: a1b2c3d]` |
| `[P]` | Parallelizable — multiple agents may claim concurrently | `- [P] [pending] Task 9: ...` |

## Decision Log Entry Types

The Decision Log is the **lock file** that stops stateless agents from undoing deliberate choices. Every entry opens with a bracketed type tag and a date.

| Type | When to use | Template |
|---|---|---|
| `[DELETION]` | Removed something deliberately — future agents must not re-add it | `[DELETION] 2026-04-16 Removed X-endpoint. Reason: deprecated by Y. Do not re-add.` |
| `[DIRECTION]` | Chose approach X over Y for a stated reason | `[DIRECTION] 2026-04-16 Chose idempotency key over distributed lock. Reason: lock adds 80ms p99.` |
| `[SCOPE]` | Cut scope — what's in, what's explicitly out | `[SCOPE] 2026-04-16 Email notifications deferred to v2. Reason: requires SES provisioning.` |
| `[PIVOT]` | Course correction — old direction obsolete, new direction active | `[PIVOT] 2026-04-16 Was targeting Postgres; now targeting Cloudflare D1. Reason: edge-compatible.` |
| `[CONSTRAINT]` | Discovered a hard constraint (infra limit, compliance, budget) | `[CONSTRAINT] 2026-04-16 Function timeout 300s. Reason: Vercel Fluid Compute ceiling.` |
| `[REVERSAL]` | Undoing a prior Decision Log entry — reference the old one | `[REVERSAL] 2026-04-16 Revert [DIRECTION 2026-03-12]. Reason: benchmarks showed 3x regression.` |

**Why the tags matter:** a future agent scanning the Decision Log greps by tag to answer "what's forbidden?" (`[DELETION]`), "what are the architectural choices?" (`[DIRECTION]`), or "what changed recently?" (`[PIVOT]` / `[REVERSAL]`).

## Surprise Entry Format

Unexpected findings from execution. Timestamped, short, actionable.

```
- [YYYY-MM-DD] Found: X. Impact: Y. Plan update: Z.
```

Each entry has all three fields — a finding without impact is a journal note, not a surprise; an impact without a plan update leaves the plan out of sync with reality.

## Progress Entry Format

One line per cycle. Leaner than a checkpoint commit — the diff tells the story, the Progress line orients future agents.

```
- [YYYY-MM-DD HH:MM] What happened. Next: what's next. Blocker: if any.
```

**Do:**
- Open with a verb (shipped, investigated, blocked, promoted, archived)
- Reference task numbers: `shipped Task 7`
- Cite files when the reader needs them: `see fix at src/auth.ts:42`

**Don't:**
- Summarize the diff — that's what `git log` is for
- Write "everything fine" lines — if there's nothing to report, don't add an entry
- Paraphrase the plan — reference it by task number instead

## Evidence Source Tags

Every item in the Evidence section cites a source. Standard tags:

| Tag | Points to |
|---|---|
| `[Source: codebase grep]` | A grep hit in the repo, format `file:line pattern` |
| `[Source: GitHub PR #N]` | A comment, review, or decision on a PR |
| `[Source: GitHub issue #N]` | An issue report or discussion |
| `[Source: Sentry <id>]` | A Sentry issue with occurrences + user impact |
| `[Source: design doc]` | An architecture or product doc (inline quote preferred) |
| `[Source: team chat]` | A Slack / Linear / email decision (screenshot or quote) |
| `[Source: measurement]` | A benchmark, perf measurement, or experiment result |

**Rule:** a plan entry without a source is a guess. Guesses cause rework (SKILL.md Principle 1).

## Constraints Block Format

Two subsections — things that must be true, things that are forbidden.

```markdown
## Constraints
- ALWAYS: integration tests hit the real database (no mocks)
- ALWAYS: run lint + build before commit
- NEVER: edit content/posts/**/*.mdx body text
- NEVER: skip pre-commit hooks
```

**Rule of thumb:** constraints survive the project. If a rule only applies to one task, put it on the task line, not in Constraints.

## Open Questions

Format: one line per question, with an action.

```markdown
## Open Questions
- Q1: Does R2 support signed URLs with custom domains? → Action: grep R2 docs, or test in a scratch script
```

Each question has an **action** — someone or something to resolve it. An open question without an action is stalled work masquerading as a plan.

## Compound Task Sub-Plan Structure

When a task has `[Investigation: investigations/<slug>.md]`, the sub-plan follows this structure:

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

Sections fill in as the investigation progresses. **No `## Fix Spec` → no code** — the cycle is investigation-only until the spec lands. See [SKILL.md § Investigation Template](../../SKILL.md#investigation-template) for the full contract.

## See Also

- [SKILL.md](../../SKILL.md) — the five principles and the cycle
- [Prompt Template](prompt-template.md) — the 8-block prompt shape for a vidux worker
- [Fleet / Claude Lifecycle](../fleet/claude-lifecycle.md) — how a cycle actually fires
