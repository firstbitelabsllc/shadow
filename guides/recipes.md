# Automation Recipes

Opinionated, ready-to-deploy automation patterns for vidux fleets. Each recipe includes: when to use it, the trigger type, a complete prompt template, and the review pipeline it plugs into.

All recipes follow the ready-PR-first discipline: automation pushes open ready-for-review PRs by default, never direct-to-main. Drafts are reserved for true WIP or missing gates.

---

## Trigger Types (platform-agnostic)

These recipes describe trigger *patterns*, not specific platforms. Map them to whatever automation primitive your agent platform offers:

| Trigger pattern | Fires when | Example platforms |
|---|---|---|
| **Scheduled** | Cron expression or interval matches | CronCreate (session-scoped), cloud scheduled jobs, CI cron |
| **Event-driven** | External webhook fires (PR, push, issues, deploy, etc.) | GitHub Actions, cloud webhooks, repo hooks |
| **On-demand** | Triggered by a manual action or another automation | CLI invocation, API POST, another lane's output |

A single lane can combine triggers (e.g., scheduled nightly + fires on every new PR). The mechanics of how your platform wires triggers belong in `/vidux` Part 2 and `references/automation.md` (the platform-specific layer), not in these recipes.

---

## Recipe 1: Fleet Watcher — DEPRECATED (2026-04-17)

> ⚠️ **Deprecated.** Fleet Watcher is an orchestration smell — a scheduled lane that reads other lanes' state to report back drift the writer couldn't self-detect. In practice it adds JSONL, memory.md writes, and cross-lane reads without catching bugs the writer couldn't already see in its own logs. Fleet health belongs in the coordinator's own cycle (it already scans its own queue each fire), or in a one-shot manual audit — not a standing scheduled lane. Keep this recipe for reference only. Do not build new Fleet Watcher lanes.

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

**What:** Automated code review pipeline triggered when an automation lane creates or updates a PR. Combines review-bot output, an architecture review agent, and mechanical checks into a single structured verdict.

**Trigger:** Event-driven — PR opened or synchronized. Filter to automation branches only (convention: `claude/`, `codex/`, or `auto/` prefix).
**Role:** Reviewer (read-only, never pushes code)

### Prompt Template

```
Use vidux as PR reviewer.

Mission: Review PRs from automation lanes. Post structured feedback.
Never approve, never merge unless this lane's authority explicitly allows it.

WHEN TRIGGERED (PR opened or updated):
1. Read the PR diff: gh pr diff <number>
2. Read the linked plan task (PR body carries task ID)

REVIEW PIPELINE (run all three, combine results):

Step 1 — Code review bot output:
  If an AI code-review bot is wired to the repo, read its comments.
  Extract: issues found, severity, suggested fixes.

Step 2 — Architecture review:
  Spawn a code-review agent with the diff.
  Check: scope creep, missing tests, style drift, security.

Step 3 — Mechanical checks:
  - Does diff touch only files listed in the task spec?
  - Do new functions have test coverage?
  - Any TODO/FIXME/HACK added without a plan task?
  - Any secrets, .env files, or credentials in the diff?

POST REVIEW as PR comment:
  ## Automated Review
  **Bot review:** [pass/issues] — <summary>
  **Architecture:** [pass/issues] — <summary>
  **Mechanical:** [pass/issues] — <summary>
  **Verdict:** READY_FOR_HUMAN | NEEDS_WORK | BLOCKED

If NEEDS_WORK: add inline review comments on specific lines.
If BLOCKED: label the PR and flag in the fleet watcher's next cycle.
Never approve. Never merge. Never mark ready-for-review.
```

### When to Use

Every fleet that creates automation PRs. This is the quality gate between "automation wrote code" and "merge." Without it, humans review raw diffs with no context. With it, reviewers get a pre-screened summary and only inspect what matters.

### Review Bot Setup (optional)

If an AI code-review bot or static-analysis service is wired to the repo, this recipe reads its comments in the Bot review step. Otherwise, the Architecture + Mechanical checks still provide value. Specific review-service wiring lives in `/vidux` Part 2 and `references/automation.md` where platform specifics belong.

---

## Recipe 3: PR Lifecycle Manager

**What:** Tracks all open automation PRs across repos. Detects stale drafts, monitors CI status, and surfaces PRs ready for merge.

**Trigger:** Scheduled, every 1 hour
**Role:** Coordinator or tracker (merge only if the lane authority explicitly allows it)

### Prompt Template

```
Use vidux to track PR lifecycle across all repos.

Mission: No PR goes stale. Every reviewed PR gets merged, fixed, or closed.

READ:
1. For each repo in scope: gh pr list --state open --json number,title,isDraft,createdAt,headRefName,statusCheckRollup
2. Filter to PRs from automation lanes (branch prefix convention: claude/, codex/, auto/)
3. Read PR comments for review verdicts (READY_FOR_HUMAN / NEEDS_WORK / BLOCKED)

CLASSIFY each PR:
- FRESH: created < 24h ago, no review yet -> waiting for PR Reviewer
- REVIEWED: has review verdict → action depends on verdict
- DRAFT: still draft after local gates passed -> run or request `gh pr ready <N>`
- STALE: created > 48h ago with no activity -> flag for cleanup
- FAILING: CI checks failing -> flag for investigation
- READY: review passed + CI green -> merge if lane authority allows, otherwise notify promoter

ACTION:
- READY PRs: merge when authorized, otherwise post a summary to the promoter's preferred notification channel (email, Slack, or plain digest)
  "3 PRs ready: <project-a>#283, <project-b>#44, <project-c>#12"
- STALE PRs: add comment "This PR has been open 48h+ with no activity. Close or update."
- FAILING PRs: check if the failure is flaky (re-run) or real (flag for the owning lane)

OUTPUT: PR dashboard — one line per open PR with status + age + review verdict.

Never merge a draft, failing PR, or PR with unaddressed required review findings. Never approve. Never close unless explicitly stale > 7 days with no commits.
```

### When to Use

Any fleet using ready-PR-first discipline. Without a lifecycle manager, PRs accumulate silently. The fleet keeps creating new PRs while old ones rot.

---

## Recipe 4: Observer Pair — DEPRECATED (2026-04-17)

> ⚠️ **Deprecated.** Observer Pair is the same orchestration smell as Fleet Watcher applied per-writer. Extra memory.md files, cadence-offset cycles, and cross-lane reads for bugs the writer couldn't see — in practice observers catch far less drift than expected and most of what they do catch is better fixed by editing the writer's prompt. See `references/automation.md` Section 3 / Section 8. Do not build new Observer Pair lanes.

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

### Secondary-Model Delegation

For large plan stores (>3 KB), delegate the READ step to a secondary model via `/vidux` Part 2 Mode A. Observer reads the compressed summary instead of the raw files. Keeps the primary model's budget tight.

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
Recommend actions; let the fleet watcher or a human execute.
```

---

## Recipe 7: Skill Refiner

**What:** Periodic quality sweep of skill files. Checks description quality (drives activation rates), stale references, and cross-ref consistency.

**Trigger:** Scheduled, every 6 hours
**Role:** Quality auditor (writes to skill files via PR only)

### Prompt Template

```
Use vidux as skill refiner for ~/Development/ai/skills/.

Mission: Every skill's description drives its activation rate. Polish descriptions,
fix stale refs, ensure cross-refs are valid. Ship improvements as ready PRs after local gates pass.

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
6. gh pr create --title "skill(<name>): <improvement>" --body "<audit findings>"

ONE skill per cycle. Rotate through the full list over 24-48 hours.
Never delete a skill without the human operator's explicit approval.
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
- Are any guides stale (referencing deprecated automation primitives or superseded patterns)? → update them
- Are tests failing? → fix them first

ACT:
- Trivial doc fixes → commit directly to main
- Substantial changes → branch + ready PR
- Always commit as: vidux: self-improvement — <what changed>

VERIFY:
- Run tests if they exist: python -m pytest tests/
- Check that referenced files/paths are valid
- Ensure README claims match reality

CHECKPOINT:
- Update PLAN.md Progress section
- If all [pending] tasks are done → go IDLE (don't invent work)
- After 2 consecutive IDLE cycles → routine should reduce frequency or pause

Delegate to a secondary model via `/vidux` Part 2 Mode B for any change >10 lines.
```

---

## Composing Recipes into a Fleet

A typical production fleet combines 3-5 recipes:

```
┌─────────────────────────────────────────────────────────┐
│                 Production Fleet                        │
│                                                         │
│  Scheduled (every 1-6h):                                │
│    PR Lifecycle ──→ stale detection + ready notification │
│    Trunk Health ──→ repo hygiene + worktree GC          │
│    Skill Refiner ──→ description quality + stale refs   │
│                                                         │
│  Event-driven:                                          │
│    PR Reviewer ──→ review bot + code-review agent       │
│    Deploy Watcher ──→ verify after merge (with EXIT)    │
│                                                         │
│  Meta:                                                  │
│    Self-Improvement ──→ vidux improving vidux (24h)     │
└─────────────────────────────────────────────────────────┘
```

### Cadence Planning

Every automation platform has caps — daily run limits, webhook-per-hour limits, token budgets, or session lifetime. Plan cadences with headroom:

| Recipe | Trigger | Est. fires/day | Notes |
|---|---|---|---|
| PR Reviewer | Event-driven | ~5 | Per PR from automation |
| PR Lifecycle | Scheduled 1h | 24 | Drop to scheduled 2h if cap-constrained |
| Deploy Watcher | Event-driven | ~3 | Exits after verification (max 3 checks) |
| Trunk Health | Scheduled 4h | 6 | Light — mostly git status checks |
| Skill Refiner | Scheduled 6h | 4 | One skill per cycle |
| Self-Improvement | Scheduled 24h | 1 | Meta — vidux improving vidux |

**Cadence strategy:** Start with PR Reviewer + PR Lifecycle (highest ROI). Add recipes as you verify the platform's caps support them.

### Hybrid Strategy: Persistent + Session-scoped

Not everything needs a persistent cloud lane. Use session-scoped automation (e.g., CronCreate) for:
- Short experiments ("run this for the next 2 hours")
- Rapid iteration on a new recipe before promoting it to a persistent lane
- Anything that needs access to local-only resources (Xcode, simulators, local builds)

Use persistent cloud lanes (or a persistent local runner) for:
- Anything that must survive laptop close
- Event-driven triggers (session-scoped cron can't do webhooks)
- Fleet watchers and lifecycle managers (must be always-on)

---

## Recipe 9: Edit-Then-Verify

**When to use:** Any automation lane that edits state files (memory.md, PLAN.md, JSONL) where concurrent writers exist.

**Pattern:** After every file edit, immediately re-read the file to verify the change applied. If the re-read shows unexpected content, log the mismatch to memory and retry with fresh content.

```
Write to memory → re-read memory → compare expected vs actual
  match → continue
  mismatch → log to memory, re-read full file, retry edit (max 3 attempts)
  3 failures → mark lane degraded, checkpoint, exit
```

**Exit condition:** 3 consecutive edit-verify failures on the same file = lane exits with DEGRADED status. Do not retry indefinitely.

**Why:** Edit whitespace mismatches are the #1 friction type in fleet operations (observed in 2/10 sessions). The re-read step catches stale content before it corrupts state.

---

## Recipe 10: Cron Retry with Backoff

**When to use:** Any cron lane that encounters transient failures (auth expiry, rate limits, external service timeouts, context overflow).

**Pattern:** When a cycle exits due to an external blocker or context overflow, back off and retry once. If the retry also fails, mark the task `[blocked]` and exit.

```
Cycle fails with external_blocker or context_overflow
  → checkpoint failure reason to memory.md
  → wait 5 minutes (ScheduleWakeup if same-session, next CronCreate fire if lane-based)
  → retry once with fresh context
  → second failure → mark task [blocked], add Decision Log entry, exit
```

**Exit condition:** Max 1 retry per failure. Two consecutive failures = blocked. Never retry in a tight loop.

**Why:** Transient failures (auth, rate limits) often resolve within minutes. One retry catches those. Persistent failures (wrong config, missing permissions) need human intervention — retrying wastes cycles.

---

## Recipe 11: Multi-PR Dependency Shipping

**When to use:** When a coordinator lane manages 3+ open PRs with merge-order dependencies (e.g., shared types must merge before consumers, migration must merge before the code that reads new schema).

**Pattern:** Build a dependency DAG from changed files, then ship in topological order.

```
1. List open PRs: gh pr list --state open --author @me
2. For each PR, get changed files: gh pr diff <N> --name-only
3. Build dependency edges:
   - PR A touches shared types → PR B imports those types → B depends on A
   - PR A adds a migration → PR B reads new columns → B depends on A
4. Topological sort: ship roots first (no dependencies)
5. For each root PR:
   - Verify CI green (or run local checks for repos without CI)
   - If all review comments addressed → post READY_FOR_MERGE comment
6. After root merges → rebase dependents, re-verify, repeat
```

**Exit condition:** All PRs either merged or marked `[blocked]` with reason. Never hold a PR queue open indefinitely — if a root PR is blocked for 2+ cycles, escalate.

**Why:** Manual dependency tracking across 5+ PRs causes ordering mistakes (merge consumer before provider → broken build). The DAG makes it mechanical.

---

## Anti-Patterns

**1. Unsafe auto-merge.** Never merge a draft, failing PR, or PR with unaddressed required review findings. Personal overlays may authorize auto-merge after checks are green and findings are acked/resolved.

**2. Stuck verification loop.** Deploy watchers that re-verify 300+ times. Every recipe with a verification step MUST have an EXIT CONDITION with a max retry count.

**3. Ledger noise.** Lanes that log every heartbeat. Log once when idle, not per-fire. (Lesson from 395K empty `vidux_loop_start` entries.)

**4. Fabricated evidence.** Lanes that invent memory files or audit results to justify actions. COPY SAFETY applies to all automation output.

**5. Direct-to-main pushes.** All automation code changes go through PRs. The only exception is explicitly authorized human/local policy. Never let automation fall back to pushing main.

**6. Prompt bloat.** Recipe prompts should be under 30 lines. The vidux skill handles the cycle mechanics — prompts specify role, mission, and boundaries. Don't restate doctrine.
