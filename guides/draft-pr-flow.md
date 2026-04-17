# Draft-PR Flow — Core Doctrine

Cloud-agnostic. Works with any git remote that supports `gh pr create`. No paid-service dependencies.

## Why

Local worktrees are ephemeral. Crashes, disk cleanup, and `git worktree remove` destroy in-progress work silently. Draft PRs on GitHub are the durable manifest — `gh pr list` shows every lane's in-flight work, the diff, and where to resume.

Secondary: forces human review before code reaches main. Eliminates the COPY SAFETY incident class (direct-to-main automation pushes with hallucinated content).

## The flow

Every automation lane that ships code follows this after a green build + test:

```
1. Push the worktree branch to origin:
   git push origin HEAD:claude/<lane-name>-<task-id>

2. Create a draft PR:
   gh pr create --draft \
     --base main \
     --head "claude/<lane-name>-<task-id>" \
     --title "[<lane-name>] <task summary>" \
     --body "## Automation
   Lane: <lane-name>
   Plan task: <task-id>
   Resume point: <what the next cycle should do if this PR stalls>

   ## Changes
   <1-3 bullet summary>"

3. Do NOT merge to main locally.
   The draft PR is the delivery. A human merges after review.

4. Before each cycle, sync local main:
   git pull origin main

5. Delete the worktree after pushing.
```

## Branch naming

`claude/<lane-name>-<task-id>` — predictable, greppable, lane-attributable.

Examples:
- `claude/coach-p0-T3`
- `claude/resplit-bug-fixer-ABv07GVF`
- `claude/web-executor-5.2.1`

## PR body template

The body MUST carry three fields so any agent (or human) can resume:

| Field | Purpose |
|---|---|
| **Lane** | Which automation created this PR |
| **Plan task** | Which PLAN.md task this addresses |
| **Resume point** | What the next cycle should do if the PR stalls |

## Recovery via `gh pr list`

When a worktree is lost:
```bash
gh pr list --state open --json number,title,isDraft,headRefName --jq '.[]'
```

Each open draft PR is a recoverable unit of work. To resume:
```bash
gh pr checkout <number>
```

## Fallback

If `gh pr create` fails (auth issue, network, no `gh` CLI):
1. Push the branch anyway: `git push origin HEAD:claude/<lane-name>-<task-id>`
2. Log the failure in the lane's `memory.md`
3. Do NOT fall back to pushing main
4. The next cycle retries the PR creation against the existing branch

## What this does NOT cover

- Who reviews the PR (human — always, per Q3 confirmed 2026-04-11)
- Auto-merge policy (never — per Q4 confirmed 2026-04-11)
- Paid-service integrations (Greptile review, Sentry context) — those live in `/vidux` Part 2 scope as composable add-ons
- Leo's personal pushes (unchanged — Phase 5 is automation-only per Q6)

## Adopting this in a lane prompt

Replace any existing push policy with:

```
**PUSH POLICY (draft-PR-first per vidux Phase 5):**
After green build + test in the worktree:
1. Push branch: `git push origin HEAD:claude/<lane>-<task-id>`
2. Draft PR: `gh pr create --draft --base main --head "claude/<lane>-<task-id>" --title "[<lane>] <summary>" --body "..."`
3. NEVER push directly to origin/main.
4. Sync before each cycle: `git pull origin main`
5. Fallback: if `gh pr create` fails, push branch only, log failure. Never push main.
```

Replace any "merge to main before stopping" instruction with "push branch + create draft PR."

## Validated

Tested end-to-end 2026-04-12 on `leojkwan/vidux` (PR #4). Zero friction. Branch push, draft PR creation, `gh pr list` visibility, close + cleanup all worked cleanly.
