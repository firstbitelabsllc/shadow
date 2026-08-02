# Pilot Puppy Quick Start

Install Pilot Puppy, create an owning plan, and leave a cold-resume handoff.

## 1. Install Pilot Puppy

Pilot Puppy is an agent skill first: it gives the coding host the
plan/proof/resume contract. Mount the stable `vidux` compatibility skill once
in the tested host:

```bash
git clone https://github.com/firstbitelabsllc/vidux.git ~/Development/vidux
mkdir -p "$HOME/.claude/skills"
ln -sfn "$HOME/Development/vidux" "$HOME/.claude/skills/vidux"
```

This quick start covers the Claude Code skill mount. Pilot Puppy's shared direct
Cursor adapter has a separate bounded host-receipt proof; it does not turn
the compatibility core into a provider runtime. Use
[`SKILL.md`](https://github.com/firstbitelabsllc/vidux/blob/main/SKILL.md) as
the Pilot Puppy contract. The `vidux` command remains the stable compatibility
CLI. To add it to your PATH:

```bash
mkdir -p "$HOME/.local/bin"
ln -sfn "$HOME/Development/vidux/bin/vidux" "$HOME/.local/bin/vidux"
export PATH="$HOME/.local/bin:$PATH"   # add to your shell profile to keep it
vidux --version
```

See [Installation](/guide/installation) for an optional locally-built tarball
(`npm pack`) that does not require keeping the checkout on `PATH`.

## 2. Start a Pilot Puppy session

Claude Code is the tested skill host. Open it in the repository and request:

```
/vidux "your project description"
```

The skill should read repository instructions and reuse an existing `PLAN.md`.
If none exists, it can scaffold one and replace the starter row with a concrete
outcome and gate before editing code. The coding host—not the Pilot Puppy
compatibility core—executes the work.

The same local plumbing is available directly when you'd rather drive it
yourself:

```bash
cd /path/to/your-project   # the repo you want Pilot Puppy to track
vidux init --here
vidux status
vidux browse --root .   # loopback, read-mostly local cockpit
```

## 3. Understand the Startup Contract

The skill resolves repository state before the coding host acts:

1. Read repository instructions and the owning `PLAN.md`.
2. Inspect the current revision and working tree.
3. Read the proof named by the active row.
4. Resume `[in_progress]`; otherwise select the highest unblocked row.

Pilot Puppy does not select a model, launch a worker, schedule a session, or manage
provider authentication. Those are coding-host responsibilities.

## 4. Establish the First Row

`vidux init --here` creates `PLAN.md` only when it is missing. Its starter row
is deliberately unproven. Replace it with a bounded outcome and a real gate:

> **A plan entry without evidence is a guess. Guesses cause rework.**

```markdown
# My Project

## Purpose
Ship a rate limit for the login endpoint without changing other routes.

## Evidence
- [Source: codebase grep] src/auth/login.ts:42 — missing rate limit

## Constraints
- Keep existing authentication behavior.

## Operator Brief
- Status: working
- Outcome: Login bursts receive a bounded response.
- Next: Add the smallest rate-limit change and its regression test.
- Validation: Run the named login test and a six-request manual check.

## Outcome Scorecard
| Metric | Baseline | Current | Target | Status | Proof |
|---|---|---|---|---|---|
| Sixth burst request | unbounded | unproven | HTTP 429 | unproven | test output |

## Tasks
- [pending] T-1: Add and prove login rate limiting.

## Decision Log
## Progress
```

## 5. Run One Bounded Cycle

For the selected row:

1. **READ**: inspect the plan, revision, working tree, and named proof.
2. **ASSESS**: resume the active row or select one unblocked row.
3. **ACT**: make one bounded, reversible change.
4. **VERIFY**: run the row's real gate.
5. **CHECKPOINT**: record result, proof, uncertainty, and one next move in
   repository files, then exit.

When code changed, the local commit stays concise:

```
vidux: add rate limiting to login endpoint

- Added express-rate-limit middleware to /auth/login
- Added a focused regression test
- Proof: the named login test passes
```

The durable handoff is the owning `PLAN.md`, linked proof, and Git revision.

### Optional checkpoint helper

For a task whose text already appears in the plan:

```bash
vidux checkpoint PLAN.md "T-1: Add and prove login rate limiting." \
  "login test and manual check passed" \
  --proof "focused test passed; first request beyond the limit returned 429"
```

Completion requires `--proof`; a blocked checkpoint requires a concrete
`--blocker`. The helper updates the task and Progress entry and leaves them
uncommitted by default. `--commit` stages the plan and asks Git to create a
commit; review the existing index first.

If a local ledger is configured, the helper may append a row. Local `done` maps
to `needs_review`, not an open pull request or shipped state. The row is an
optional local projection; it is not authority and is never a publication gate.

## 6. Resume After an Interruption

Pilot Puppy does not auto-recover a session. A new reader reconstructs state by
reading `PLAN.md`, checking the current revision and working tree, and opening
the row's linked proof. Preserve unexplained work before editing or creating a
duplicate lane.

## 7. When All Tasks Complete

Verify the plan's stated outcome and final gate, record the result, and stop.
Finding or scheduling more work is a coding-host or maintainer decision, not an
automatic compatibility-runtime behavior.

## Common Patterns

These are tested-host skill requests, not CLI flags.

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
/vidux "investigate performance issues in the dashboard. Plan only, no code this cycle."
```

No `/vidux --plan` CLI flag exists. For a planning-only pass, say so in the
skill request.

## Next Steps

- [Five Principles](/concepts/principles) — the doctrine behind the discipline
- [The Cycle](/concepts/cycle) — detailed step-by-step mechanics
- [PLAN.md Structure](/concepts/plan-structure) — full template reference
