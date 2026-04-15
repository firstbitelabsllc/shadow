# Automation Recipes

Opinionated, ready-to-deploy automation patterns for vidux fleets. Each recipe includes: when to use it, the trigger type, a complete prompt template, and the review pipeline it plugs into.

These recipes assume **Claude Routines** as the automation primitive (cloud-native, persistent, three trigger types). CronCreate still works for session-scoped experiments but Routines are the production path.

All recipes follow the draft-PR-first discipline: automation pushes go through `gh pr create --draft`, never direct-to-main. Human promotes.

---

## How Routines Work

Claude Routines run on Anthropic-managed cloud infrastructure — they survive when your laptop closes. Each routine is a saved configuration: a prompt, one or more repositories, a cloud environment, MCP connectors, and triggers.

> Routines are in research preview. Behavior, limits, and the API surface may change.

| Trigger type | Fires when | Create via |
|---|---|---|
| **Scheduled** | Cron expression matches (min 1h interval, presets: hourly/daily/weekdays/weekly) | CLI (`/schedule`) or web |
| **GitHub event** | Webhook fires (PR, push, issues, workflow runs, releases, discussions, check runs, merge queue, etc.) | Web UI only |
| **API** | `POST /fire` with bearer token + optional `text` payload | Web UI only |

A single routine can combine multiple triggers. For example, a PR review routine can run nightly (scheduled), trigger from a deploy script (API), and react to every new PR (GitHub).

### Key details (from [official docs](https://code.claude.com/docs/en/routines))

- **Branch permissions:** By default, routines can only push to `claude/`-prefixed branches. Enable "Allow unrestricted branch pushes" per repo if needed.
- **Daily run cap:** Per-account daily limit — check yours at [claude.ai/settings/usage](https://claude.ai/settings/usage). Organizations with extra usage enabled can keep running on metered overage.
- **Environments:** Each routine runs in a cloud environment with configurable network access, environment variables, and setup scripts. Configure at [claude.ai](https://claude.ai) before creating the routine.
- **Connectors:** All your connected MCP connectors (Slack, Linear, Google Drive, etc.) are included by default. Remove any the routine doesn't need.
- **Runs are full sessions:** No permission prompts during runs. The routine can run shell commands, use skills committed to the repo, and call any included connectors.
- **Identity:** Commits and PRs carry YOUR GitHub user. Slack/Linear actions use YOUR linked accounts.

### CLI commands

```
/schedule                      # Create a new scheduled routine (interactive)
/schedule daily PR review      # Create with description
/schedule list                 # List all routines
/schedule update               # Update an existing routine
/schedule run                  # Trigger a routine immediately
```

### API trigger example

```bash
curl -X POST https://api.anthropic.com/v1/claude_code/routines/trig_01ABCDEF.../fire \
  -H "Authorization: Bearer sk-ant-oat01-xxxxx" \
  -H "anthropic-beta: experimental-cc-routine-2026-04-01" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"text": "Sentry alert SEN-4521 fired in prod. Stack trace attached."}'
```

Returns: `{ "claude_code_session_id": "...", "claude_code_session_url": "..." }`

### GitHub trigger — supported events

| Event | Triggers when |
|---|---|
| Pull request | PR opened, closed, assigned, labeled, synchronized |
| Push | Commits pushed to a branch |
| Issues | Issue opened, edited, closed, labeled |
| Release | Release created, published, edited |
| Workflow run | GitHub Actions workflow starts or completes |
| Check run/suite | Check run created or completed |
| Discussion | Discussion created, edited, answered |
| Merge queue | PR enters or leaves merge queue |

PR filters: author, title, body, base branch, head branch, labels, is_draft, is_merged, from_fork. All conditions must match.

---

## Recipe 1: Fleet Watcher

**What:** Scheduled health check across all automation lanes. Reads memories, classifies fleet state, escalates stuck lanes, detects trunk health issues.

**Trigger:** Scheduled, every 2 hours
**Role:** Coordinator (read-only analysis, never writes code)

### Prompt Template

```
Use vidux as coordinator for the full automation fleet.

Mission: Keep the fleet making fire, not rubbing sticks.

READ (every cycle):
1. Scan ~/.claude-automations/*/memory.md — last 3 entries per lane
2. Read ledger: tail -100 ~/.agent-ledger/activity.jsonl | jq for current repos
3. Check trunk health: git status + git rev-list on each target repo

CLASSIFY each lane:
- SHIPPING: produced commits in last 2 cycles
- IDLE: gate-exiting with no work, 2+ consecutive
- BLOCKED: same blocker 2+ cycles
- CRASHED: auth failure, MCP disconnect, no memory entry in 24h
- STUCK: 3+ progress entries on same task

ESCALATE:
- 3+ lanes IDLE on same plan → queue starvation, not lane problem
- Same blocker across 2+ lanes → infrastructure issue
- Any CRASHED lane → immediate flag
- Any lane STUCK → mark [blocked] in plan, flag for human

OUTPUT: Fleet scorecard — N SHIPPING / N IDLE / N BLOCKED / N CRASHED
One line per lane with status + last action + recommended intervention.

Never edit code. Never edit plans. Report and recommend only.
```

### When to Use

Any fleet with 3+ active lanes. Without a watcher, stuck lanes burn cycles silently for hours — the Apr 2026 fleet run proved this (300+ re-verifications from a stuck cron).

---

## Recipe 2: PR Reviewer

**What:** Automated code review pipeline triggered when an automation lane creates a draft PR. Runs Greptile AI review + architecture review agent, posts structured feedback.

**Trigger:** GitHub event — `pull_request.opened` + `pull_request.synchronize`. Filter: head branch contains `claude/` (automation lanes only). Configure via web UI at claude.ai/code/routines.
**Role:** Reviewer (read-only, never pushes code)

### Prompt Template

```
Use vidux as PR reviewer.

Mission: Review draft PRs from automation lanes. Post structured feedback.
Never approve, never merge — Leo promotes.

WHEN TRIGGERED (draft PR opened or updated):
1. Read the PR diff: gh pr diff <number>
2. Read the linked plan task (PR body carries task ID)

REVIEW PIPELINE (run all three, combine results):

Step 1 — Greptile review:
  Use mcp__greptile__trigger_code_review on the PR.
  Extract: issues found, severity, suggested fixes.

Step 2 — Architecture review:
  Spawn superpowers:code-reviewer agent with the diff.
  Check: scope creep, missing tests, style drift, security.

Step 3 — Mechanical checks:
  - Does diff touch only files listed in the task spec?
  - Do new functions have test coverage?
  - Any TODO/FIXME/HACK added without a plan task?
  - Any secrets, .env files, or credentials in the diff?

POST REVIEW as PR comment:
  ## Automated Review
  **Greptile:** [pass/issues] — <summary>
  **Architecture:** [pass/issues] — <summary>
  **Mechanical:** [pass/issues] — <summary>
  **Verdict:** READY_FOR_LEO | NEEDS_WORK | BLOCKED

If NEEDS_WORK: add inline review comments on specific lines.
If BLOCKED: label the PR and flag in the fleet watcher's next cycle.
Never approve. Never merge. Never mark ready-for-review.
```

### When to Use

Every fleet that creates draft PRs. This is the quality gate between "automation wrote code" and "Leo reviews." Without it, Leo reviews raw diffs with no context. With it, Leo gets a pre-screened summary and only reviews what matters.

### Greptile Setup

Requires the Greptile MCP server connected. Greptile indexes the repo and provides AI-powered code review that understands the full codebase context — not just the diff.

```
mcp__greptile__trigger_code_review — triggers review on a PR
mcp__greptile__list_code_reviews — check review status
mcp__greptile__search_greptile_comments — find past review patterns
```

---

## Recipe 3: Draft-PR Lifecycle Manager

**What:** Tracks all open draft PRs across repos. Detects stale drafts, monitors CI status, notifies when PRs are ready for promotion.

**Trigger:** Scheduled, every 1 hour
**Role:** Tracker (read-only)

### Prompt Template

```
Use vidux to track draft-PR lifecycle across all repos.

Mission: No draft PR goes stale. Every reviewed PR gets promoted or closed.

READ:
1. For each repo Leo owns: gh pr list --state open --json number,title,isDraft,createdAt,headRefName,statusCheckRollup
2. Filter to draft PRs from automation lanes (branch prefix: claude/, codex/)
3. Read PR comments for review verdicts (READY_FOR_LEO / NEEDS_WORK / BLOCKED)

CLASSIFY each draft PR:
- FRESH: created < 24h ago, no review yet → waiting for PR Reviewer
- REVIEWED: has review verdict → action depends on verdict
- STALE: created > 48h ago with no activity → flag for cleanup
- FAILING: CI checks failing → flag for investigation
- READY: review passed + CI green → notify Leo

ACTION:
- READY PRs: post a summary to Leo (maily or Slack if available)
  "3 draft PRs ready for promotion: #283 (strongyes), #44 (ai), #12 (resplit)"
- STALE PRs: add comment "This PR has been open 48h+ with no activity. Close or update."
- FAILING PRs: check if the failure is flaky (re-run) or real (flag for the owning lane)

OUTPUT: PR dashboard — one line per open draft with status + age + review verdict.

Never merge. Never approve. Never close (unless explicitly stale > 7 days with no commits).
```

### When to Use

Any fleet using draft-PR-first discipline. Without a lifecycle manager, draft PRs accumulate silently. Leo doesn't see them. The fleet keeps creating new PRs while old ones rot.

---

## Recipe 4: Observer Pair

**What:** Read-only audit of a writer lane's plan, progress, and memory files. Catches what the writer can't see from inside its own worldview.

**Trigger:** Scheduled, offset from writer cadence (e.g., writer every 1h, observer every 2h at :30 offset)
**Role:** Observer (strictly read-only, never edits code or plan)

### Prompt Template

```
Use vidux as observer for <writer-lane-name>.

Mission: Catch what the writer can't see. Independent eyes on the same files.

READ (fresh each cycle — no memory of prior reads):
1. Writer's PLAN.md — task statuses, FSM compliance
2. Writer's PROGRESS.md or Progress section — chronological order, shipping signal
3. Writer's memory.md — consistency with plan state
4. Recent git log on writer's repo — do commits match claimed progress?
5. Latest ledger entries for the writer's agent_id

AUDIT CHECKLIST:
- [ ] FSM compliance: tasks follow pending → in_progress → completed. No jumps.
- [ ] Progress is chronological (timestamps in order)
- [ ] No retroactive rewrites of progress or memory (append-only rule)
- [ ] Claimed completions match actual git commits
- [ ] No strategic drift (writer doing polish when queue has gaps elsewhere)
- [ ] No scope creep (writer touching files outside its role boundary)
- [ ] Decision Log entries not contradicted by recent actions
- [ ] Evidence citations still valid (files exist, line numbers correct)

OUTPUT (3-section audit):
1. Summary: 3 sentences MAX — overall health of the writer lane.
2. Findings: specific issues with file:line references.
3. Verdict: SHIPPING | IDLE | WARNING | BLOCKED | CRASHED

Write audit to: evidence/observer-audit-<timestamp>.md in the writer's plan store.
The writer reads the latest audit at the top of each cycle.
If verdict=WARNING, the writer addresses the finding before any other task.

NEVER edit code. NEVER edit the plan. NEVER touch the writer's files except the audit output.
```

### When to Use

Every writer lane that runs unattended for 4+ hours. The Frankenstein experiment (2026-04-11) proved 100% signal-to-noise across 38 audits. Observers catch: wrong flags, non-chronological progress, stale refs, FSM violations, strategic drift.

### Codex Delegation

For large plan stores (>3 KB), delegate the READ step to `codex exec --sandbox read-only` via `/vidux-codex` Mode A. Observer reads the compressed summary instead of the raw files. Keeps Claude's budget tight.

---

## Recipe 5: Deploy Watcher

**What:** Monitors deployment status after a PR merges to main. Has a hard exit condition — once verified, it stops.

**Trigger:** GitHub event — `push` to main branch
**Role:** Verifier (read-only, time-bounded)

### Prompt Template

```
Use vidux as deploy watcher.

Mission: Verify deployment succeeded after merge. Exit after confirmation.

WHEN TRIGGERED (push to main):
1. Identify the merged PR from the push commit
2. Check deployment platform:
   - Vercel: vercel inspect or check deploy URL
   - App Store: check fastlane status or TestFlight
   - Custom: check the repo's deploy mechanism

VERIFY:
- Is the deployment live?
- Does the deployed version match the merged commit SHA?
- Any error logs in the first 5 minutes?

EXIT CONDITIONS (CRITICAL — learned from Apr 2026 incident):
- Deployment verified successfully → log to ledger, EXIT. Do not re-verify.
- Deployment failed → log failure, create [blocked] task in PLAN.md, EXIT.
- 3 checks with no deployment detected → log timeout, EXIT.
- NEVER verify more than 3 times. The stuck cron that re-verified 300+ times
  is the anti-pattern this recipe prevents.

OUTPUT: One ledger entry with deploy status + commit SHA + verification time.

After EXIT, this routine does not fire again until the NEXT push to main.
```

### When to Use

Any repo with automated deployments. Without an exit condition, deploy watchers become the #1 source of wasted cycles (proven in production).

---

## Recipe 6: Trunk Health

**What:** Periodic check of repository health: dirty checkouts, diverged branches, stale worktrees, failing CI.

**Trigger:** Scheduled, every 4 hours
**Role:** Infrastructure monitor (read-only)

### Prompt Template

```
Use vidux for trunk health monitoring across all active repos.

Mission: Catch infrastructure rot before it blocks the fleet.

CHECK (for each repo in ~/Development/ with active automation):
1. Trunk status: git -C <repo> status --short --branch
2. Divergence: git rev-list --count HEAD..origin/main (behind) and origin/main..HEAD (ahead)
3. Stale worktrees: git worktree list | count entries older than 24h
4. CI status: gh run list --limit 3 -- is the latest green?
5. Branch hygiene: git branch -r | count automation branches (claude/*, codex/*) not merged

CLASSIFY each repo:
- HEALTHY: clean trunk, not diverged, CI green, < 5 stale worktrees
- WARNING: dirty trunk OR diverged > 5 commits OR CI red
- CRITICAL: diverged > 20 commits OR 10+ stale worktrees OR trunk dirty with uncommitted plan changes

ACTION:
- WARNING repos: log finding, recommend fix
- CRITICAL repos: create [blocked] task in the repo's PLAN.md
- Run ledger --gc --report for worktree health
- Run ledger --hygiene --dry-run for branch cleanup recommendations

OUTPUT: Repo health dashboard — one line per repo with status + recommended action.

Never force-push. Never delete branches without confirmation. Never reset --hard.
Recommend actions; let the fleet watcher or Leo execute.
```

---

## Recipe 7: Skill Refiner

**What:** Periodic quality sweep of skill files. Checks description quality (drives activation rates), stale references, and cross-ref consistency.

**Trigger:** Scheduled, every 6 hours
**Role:** Quality auditor (writes to skill files via draft PR only)

### Prompt Template

```
Use vidux as skill refiner for ~/Development/ai/skills/.

Mission: Every skill's description drives its activation rate. Polish descriptions,
fix stale refs, ensure cross-refs are valid. Ship improvements as draft PRs.

READ:
1. List all skills: ls ~/Development/ai/skills/*/SKILL.md
2. For each: extract name, description, last-modified date
3. Check activation signals: grep across lane prompts for skill references

AUDIT (pick ONE skill per cycle — rotate through the list):
- Description quality: is it specific enough to trigger correctly? (20%→90% with good descriptions per Anthropic research)
- Stale references: do file paths and function names in the skill still exist?
- Cross-refs: do sibling skill references point to valid skills?
- Length: is the skill concise or bloated? (vendor guidance: "earn your complexity")

FIX (if issues found):
1. cd ~/Development/ai && git pull --rebase
2. Edit the skill file
3. git checkout -b claude/skill-refine-<name>
4. git add -A && git commit -m "update: <skill> — <what changed>"
5. git push -u origin claude/skill-refine-<name>
6. gh pr create --draft --title "skill(<name>): <improvement>" --body "<audit findings>"

ONE skill per cycle. Rotate through the full list over 24-48 hours.
Never delete a skill without Leo's explicit approval.
Never bulk-edit — one skill, one PR, one review cycle.
```

---

## Recipe 8: Self-Improvement Loop

**What:** Vidux improving vidux. Reads its own PLAN.md, identifies improvements to the vidux repo itself, ships them.

**Trigger:** Scheduled, every 24 hours (or API-triggered after a fleet run)
**Role:** Meta-writer (writes to vidux repo only)

### Prompt Template

```
Use vidux to improve vidux itself.

Mission: One improvement per cycle. Read the plan, pick the highest-priority
unfinished item, do the work, commit, push.

READ:
1. PLAN.md in ~/Development/vidux — find [pending] tasks
2. git log --oneline -10 — see what other lanes shipped recently
3. README.md — check for stale claims or missing coverage

ASSESS:
- Is there a [pending] task with evidence? → execute it
- Is the README inconsistent with current SKILL.md? → fix it
- Are any guides stale (referencing Codex automations, old patterns)? → update them
- Are tests failing? → fix them first

ACT:
- Trivial doc fixes → commit directly to main
- Substantial changes → branch + draft PR
- Always commit as: vidux: self-improvement — <what changed>

VERIFY:
- Run tests if they exist: python -m pytest tests/
- Check that referenced files/paths are valid
- Ensure README claims match reality

CHECKPOINT:
- Update PLAN.md Progress section
- If all [pending] tasks are done → go IDLE (don't invent work)
- After 2 consecutive IDLE cycles → routine should reduce frequency or pause

Delegate to codex (Mode B) for any change >10 lines.
```

---

## Composing Recipes into a Fleet

A typical production fleet combines 3-5 recipes:

```
┌─────────────────────────────────────────────────────────┐
│                    Leo's Fleet                          │
│                                                         │
│  Scheduled (every 1-6h):                                │
│    Fleet Watcher ──→ scorecard + escalation             │
│    PR Lifecycle ──→ stale detection + ready notification │
│    Trunk Health ──→ repo hygiene + worktree GC          │
│    Skill Refiner ──→ description quality + stale refs   │
│                                                         │
│  GitHub Events:                                         │
│    PR Reviewer ──→ Greptile + code-reviewer on drafts   │
│    Deploy Watcher ──→ verify after merge (with EXIT)    │
│                                                         │
│  Per Writer Lane:                                       │
│    Observer Pair ──→ independent audit of writer files   │
│                                                         │
│  Meta:                                                  │
│    Self-Improvement ──→ vidux improving vidux (24h)     │
└─────────────────────────────────────────────────────────┘
```

### Daily Budget Planning

All routine runs count against your account's daily cap (check at [claude.ai/settings/usage](https://claude.ai/settings/usage)). GitHub events beyond your hourly cap are dropped until the window resets. Plan accordingly:

| Recipe | Trigger | Est. fires/day | Notes |
|---|---|---|---|
| Fleet Watcher | Scheduled 2h | 12 | Core fleet visibility |
| PR Reviewer | GitHub event | ~5 | Per draft PR from automation |
| PR Lifecycle | Scheduled 1h | 24 | Consider CronCreate fallback to save budget |
| Observer Pair (x2) | Scheduled 2h | 12 each | Delegate reads to Codex to save tokens |
| Deploy Watcher | GitHub event | ~3 | Exits after verification (max 3 checks) |
| Trunk Health | Scheduled 4h | 6 | Light — mostly git status checks |
| Skill Refiner | Scheduled 6h | 4 | One skill per cycle |
| Self-Improvement | Scheduled 24h | 1 | Meta — vidux improving vidux |

**Budget strategy:** Start with Fleet Watcher + PR Reviewer (highest ROI). Add recipes as you verify the daily cap supports them. Use CronCreate for session-scoped work that doesn't need to survive laptop close.

### Hybrid Strategy: Routines + CronCreate

Not everything needs a cloud Routine. Use CronCreate for:
- Session-scoped experiments ("run this for the next 2 hours")
- Rapid iteration on a new recipe before promoting to Routine
- Anything that needs access to local-only resources (Xcode, simulators)

Use Routines for:
- Anything that must survive laptop close
- GitHub event triggers (CronCreate can't do webhooks)
- Fleet watchers and lifecycle managers (must be always-on)

---

## Anti-Patterns

**1. Auto-merge.** No recipe auto-merges. Ever. Leo promotes. (PLAN.md Q4)

**2. Stuck verification loop.** Deploy watchers that re-verify 300+ times. Every recipe with a verification step MUST have an EXIT CONDITION with a max retry count.

**3. Ledger noise.** Routines that log every heartbeat. Log once when idle, not per-fire. (Lesson from 395K empty `vidux_loop_start` entries.)

**4. Fabricated evidence.** Routines that invent memory files or audit results to justify actions. COPY SAFETY applies to all automation output.

**5. Direct-to-main pushes.** All automation code changes go through draft PRs. The only exception is trivial doc fixes in the vidux repo itself (and even those get a commit message prefix).

**6. Prompt bloat.** Recipe prompts should be under 30 lines. The vidux skill handles the cycle mechanics — prompts specify role, mission, and boundaries. Don't restate doctrine.
