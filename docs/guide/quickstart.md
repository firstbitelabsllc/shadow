# Quick Start

This guide walks through your first Vidux cycle from install to checkpoint.

## 1. Install Vidux

```bash
git clone https://github.com/leojkwan/vidux.git
ln -sfn /path/to/vidux ~/.claude/skills/vidux
```

## 2. Start a Session

Open Claude Code in your project directory and run:

```
/vidux "your project description"
```

**On the first cycle**, Vidux gathers evidence and writes a `PLAN.md`. No code is written until the plan is ready. This is intentional — "plan first, code second" is the core discipline.

## 3. Watch the Command Stages

`commands/vidux.md` defines six visible stages:

```
GATHER → PLAN → EXECUTE → VERIFY → CHECKPOINT → COMPLETE
```

At startup, `/vidux`:

1. Loads the `vidux` skill.
2. Reads `vidux.config.json`.
3. Resolves the authority plan store (`PLAN.md` in the repo, or a configured local/external plan store).
4. Reads the current plan, recent progress, and the git diff before deciding whether this cycle is plan creation, research, or execution.

The first run in a fresh project normally stays in `GATHER` + `PLAN`. A later run with a populated plan moves into `EXECUTE`, then `VERIFY` and `CHECKPOINT`.

## 4. The First Cycle: Evidence Gathering

The first cycle always produces a `PLAN.md`, not code. Vidux follows the rule:

> **A plan entry without evidence is a guess. Guesses cause rework.**

The agent will:
1. Grep the codebase for relevant patterns
2. Read related files
3. Check git log for recent changes
4. Synthesize findings into a structured PLAN.md

After the first cycle, you'll have a `PLAN.md` that looks like:

```markdown
# My Project

## Purpose
Why this exists. One paragraph.

## Evidence
- [Source: codebase grep] src/auth/login.ts:42 — missing rate limit
- [Source: git log] commit abc123 — "fix: auth bypass" (3 days ago)

## Tasks
- [pending] Task 1: Add rate limiting to login endpoint [Evidence: ...]
- [pending] Task 2: Write tests for auth bypass fix [Evidence: ...]

## Decisions
## Progress
```

## 5. Subsequent Cycles: Code Execution

On the second `/vidux` invocation:

1. **READ**: loads PLAN.md, checks for `[in_progress]` tasks (crash recovery)
2. **ASSESS**: first pending task has evidence → ready to code
3. **ACT**: sets task to `[in_progress]`, executes it
4. **VERIFY**: runs build and tests, shows proof
5. **CHECKPOINT**: structured commit, updates Progress log

Typical checkpoint commit:

```
vidux: add rate limiting to login endpoint
```

## 6. Crash Recovery

If a session dies mid-task, the next cycle auto-recovers:

```
CRASH RECOVERY: uncommitted work detected
git diff shows changes to src/auth/login.ts

Committing: "vidux: recover uncommitted work from crashed session"
```

The agent commits the in-progress work, then continues from the last checkpoint.

## 7. When All Tasks Complete

When the queue empties, the agent doesn't just exit — it scans for new work:

1. Checks `INBOX.md` for unprocessed findings
2. Scans owned paths for issues
3. Checks git log for changes needing follow-up
4. Rechecks blocked tasks for resolved blockers

If nothing is found, it checkpoints and exits with proof of what was scanned.

## Common Patterns

**Starting a new feature:**
```
/vidux "add dark mode support"
```

**Fixing a bug:**
```
/vidux "users report checkout double-charges on fast retry"
```

**Continuing existing work:**
```
/vidux
```
(No description needed — reads PLAN.md and resumes)

**Plan-only (no code this cycle):**
```
/vidux "plan only: investigate performance issues in the dashboard"
```
(Or simply tell `/vidux` "plan only, no code this cycle" — the command spec already distinguishes plan creation, research, and execution based on the current plan state and your instruction.)

## Next Steps

- [Five Principles](/concepts/principles) — the doctrine behind the discipline
- [The Cycle](/concepts/cycle) — detailed step-by-step mechanics
- [PLAN.md Structure](/concepts/plan-structure) — full template reference
