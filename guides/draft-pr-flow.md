# Ready-PR Flow - Core Doctrine

Cloud-agnostic. Works with any git remote that supports `gh pr create`. No paid-service dependencies.

> Historical note: this file keeps the `draft-pr-flow.md` path so old links do not break. The current doctrine is ready-PR-first; drafts are a WIP exception, not the default.

## Why

Local worktrees are ephemeral. Crashes, disk cleanup, and `git worktree remove` destroy in-progress work silently. Pull requests on GitHub are the durable manifest: `gh pr list` shows every lane's in-flight work, the diff, and where to resume.

Ready-for-review PRs also let configured review bots, preview comments, and CI gates run immediately. Draft PRs are useful only when a real gate is missing and the PR should not yet enter review.

## The Flow

Every automation lane that ships code follows this after a green local build + test:

```bash
# 1. Push the worktree branch to origin.
git push origin HEAD:claude/<lane-name>-<task-id>

# 2. Build the canonical PR body. Add --linear EVE-123 when known.
python3 scripts/vidux-pr-body.py \
  --lane "<lane-name>" \
  --task "<task-id>" \
  --resume "<what the next cycle should do if this PR stalls>" \
  --change "<1-3 bullet summary>" \
  > /tmp/vidux-pr-body.md

# 3. Open a ready-for-review PR by default.
gh pr create \
  --base main \
  --head "claude/<lane-name>-<task-id>" \
  --title "[<lane-name>] <task summary>" \
  --body-file /tmp/vidux-pr-body.md
```

Use `gh pr create --draft` only when the PR is true WIP or a required gate is missing. As soon as the gate passes, run:

```bash
gh pr ready <number>
```

Do not push directly to `origin/main`. Before each cycle, sync the local base:

```bash
git fetch --prune origin
```

Delete worktrees only after the PR branch is safely pushed and the resume point is recorded.

## Branch Naming

`claude/<lane-name>-<task-id>` or `codex/<lane-name>-<task-id>` - predictable, greppable, lane-attributable.

Examples:

- `claude/coach-p0-T3`
- `claude/resplit-bug-fixer-ABv07GVF`
- `codex/web-executor-5.2.1`

## PR Body Template

The body MUST carry these fields so any agent or human can resume:

| Field | Purpose |
|---|---|
| **Lane** | Which automation created this PR |
| **Plan task** | Which `PLAN.md` task this addresses |
| **Linear** | Optional public Linear issue id (`EVE-123`) when the task source is already known |
| **Resume point** | What the next cycle should do if this PR stalls |

## Recovery Via `gh pr list`

When a worktree is lost:

```bash
gh pr list --state open --json number,title,isDraft,headRefName --jq '.[]'
```

Each open PR is a recoverable unit of work. To resume:

```bash
gh pr checkout <number>
```

If the PR is draft and no longer blocked, flip it ready:

```bash
gh pr ready <number>
```

## Fallback

If `gh pr create` fails (auth issue, network, no `gh` CLI):

1. Push the branch anyway: `git push origin HEAD:claude/<lane-name>-<task-id>`
2. Log the failure in the lane's `memory.md`
3. Do NOT fall back to pushing main
4. The next cycle retries PR creation against the existing branch

## What This Does Not Cover

- Who reviews the PR. Use the repo's normal review-bot and human-review rules.
- Auto-merge policy. Core vidux says merge only when checks are green and required review findings are addressed; personal overlays may authorize more aggressive merging.
- Paid-service integrations. Those live in `/vidux` Part 2 scope as composable add-ons.
- Personal pushes. Human-owned flows stay under that repo's local policy.

## Adopting This In A Lane Prompt

Replace any existing push policy with:

```markdown
**PUSH POLICY (ready-PR-first per vidux):**
After green build + test in the worktree:
1. Push branch: `git push origin HEAD:claude/<lane>-<task-id>`
2. Body: `python3 scripts/vidux-pr-body.py --lane "<lane>" --task "<task-id>" --resume "<resume point>" --change "<summary>" [--linear EVE-123] > /tmp/vidux-pr-body.md`
3. Ready PR: `gh pr create --base main --head "claude/<lane>-<task-id>" --title "[<lane>] <summary>" --body-file /tmp/vidux-pr-body.md`
4. Draft only for true WIP or a missing gate; run `gh pr ready <N>` as soon as the gate passes.
5. NEVER push directly to origin/main.
6. Fallback: if `gh pr create` fails, push branch only, log failure. Never push main.
```

Replace any "stop after branch push" instruction with "push branch + create ready PR." Replace any blanket "draft PR only" instruction with "ready PR by default; draft only for WIP/missing gate."

## Validated

Draft-first was validated on 2026-04-12 via `leojkwan/vidux#4`. Ready-first supersedes that policy because modern review pipelines skip or delay work on drafts, which hides the feedback automation lanes need to nurse and merge safely.
