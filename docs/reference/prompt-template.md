# The 8-Block Prompt Template

Every vidux lane has a `prompt.md` on disk that drives each cycle. The prompt follows an 8-block structure so any agent picking up the lane knows what to read, what can abort the cycle, what it owns, and how it leaves a checkpoint behind.

For runtime mechanics, see [Claude Code Lifecycle](../fleet/claude-lifecycle.md) and [Codex Lifecycle](../fleet/codex-lifecycle.md).

## The 8 Blocks

```
1. Mission       — why this lane exists, one paragraph
2. Skills        — skill tokens this lane activates
3. Read          — files and commands to load every cycle
4. Gate          — pre-flight checks that can abort the cycle
5. Assess        — priority rules for picking the next action
6. Act           — worktree, verification, PR, and delegation rules
7. Authority     — what this lane may edit vs must never touch
8. Checkpoint    — what to append to memory.md at the end
```

Every block is required. A lane missing any of them is underspecified and will drift.

## Block 1: Mission

State the lane's job and retirement condition in one paragraph.

```markdown
## 1. Mission

Ship and maintain <project>. Every cycle either resumes an
`[in_progress]` task, fixes CI, nurses an open PR, or promotes one
inbox finding into the plan. The lane retires when the project PLAN.md
reaches its exit criteria.
```

Rules:

- Present tense, concrete, and bounded.
- Name the project or repo the lane owns.
- Name the retirement condition so the lane does not become a zombie.

## Block 2: Skills

List the skills the lane should activate before acting.

```markdown
## 2. Skills

Activate these skills every cycle, in order:
- `/vidux` — discipline + automation rules
- `/frontend-design` — only if this lane owns product UI
- `/craft-svg` — only if this lane edits inline SVG surfaces
```

Rules:

- Put `/vidux` first so the cycle and FSM load before anything else.
- Add repo-specific skills only when the lane actually uses them.
- Keep the list lean; unused skills cost context every fire.

## Block 3: Read

Spell out the exact file and command order.

```markdown
## 3. Read

Read in this order every cycle:
1. `<lane-dir>/<lane-id>/memory.md` — last 3 entries
2. `<project-root>/PLAN.md` — queue state, decisions, progress
3. `<project-root>/INBOX.md` — only when this project uses an inbox
4. `git fetch && git status --short && git log --oneline -10`
5. `gh pr list --json number,title,headRefName,statusCheckRollup`
6. sibling `memory.md` files when this lane is part of a fleet
```

Rules:

- Start with the lane's own memory file.
- Read `INBOX.md` only when the project actually uses one.
- Keep shell commands literal so the runtime can copy them exactly.

## Block 4: Gate

Define cheap checks that can abort the cycle before deeper work starts.

```markdown
## 4. Gate

Abort this cycle (append `[QC] <reason>` to memory.md and exit) if:

- Dirty tree NOT mine
  → `[QC] concurrent-cycle`
- Same task has stayed `[in_progress]` for 3+ cycles
  → mark it `[blocked]` in `## Decisions`, then exit
- Main CI is red on the latest branch head
  → fix-first mode
- Last cycle pushed a PR
  → this cycle may review CI, but not merge yet
```

Rules:

- Gates are binary: trigger or do not trigger.
- Keep the list short.
- A concurrent-cycle exit is success, not failure.

## Block 5: Assess

Make the task-selection rule deterministic.

```markdown
## 5. Assess

Priority order (first match wins):

1. Main CI red → fix the failure
2. Open PR with failing checks → nurse the PR
3. Open PR eligible for merge → merge
4. PLAN.md has `[in_progress]` work → resume it
5. PLAN.md has `[pending]` work with evidence → promote and execute
6. PLAN.md is quiet but INBOX has a promotable finding → promote it
7. Otherwise do one bounded filler audit, then exit `[IDLE]`
```

Rules:

- Pick one primary action per cycle.
- Resume `[in_progress]` work before starting something new.
- Make `[IDLE]` explicit when the queue is genuinely empty.

## Block 6: Act

This is the heavy block: worktree discipline, verification, PR flow, and any delegation rules.

```markdown
## 6. Act

### Worktree discipline
- Create a fresh worktree from `origin/main` for every code-writing task.
- Never edit the main checkout directly.

### Verification
- Run the repo's literal build/test commands before completion.
- UI work requires visual proof.

### PR flow
- Push a branch and open a ready-for-review PR by default.
- Use draft only for true WIP or a missing gate.
- Never push directly to main.

### Delegation
- Use same-runtime subagents for read-heavy or bounded code-writing tasks.
- Keep the parent lane responsible for taste, verification, and the final commit boundary.
```

Rules:

- Name verification commands literally when a specific repo requires them.
- Keep delegation same-tool and same-runtime; the current doctrine no longer uses cross-tool `codex exec` shims.
- Treat ready-PR flow as the default shipping path.

## Block 7: Authority

Tell the lane exactly what it may touch and what it must never touch.

```markdown
## 7. Authority

### May edit
- `<project-root>/app/**`
- `<project-root>/PLAN.md`
- `<project-root>/evidence/**`
- `<lane-dir>/<lane-id>/memory.md`

### Must never edit
- `.env*`
- secrets or credential files
- historical prose/content paths the repo marks as immutable
- sibling lanes' `memory.md` files
```

Rules:

- Be explicit about forbidden paths.
- Include the reason for sensitive paths when it matters.
- If the lane ships code, include the PR / push authorization boundary here or in Act.

## Block 8: Checkpoint

Define the `memory.md` append shape.

```markdown
## 8. Checkpoint

Append ONE line to `<lane-dir>/<lane-id>/memory.md`:

- [YYYY-MM-DDThh:mm:ssZ <runtime> <lane-id>] [TAG] <what happened>. <optional next step>
```

Useful tags:

- `[SHIP]`
- `[MERGED]`
- `[FIX]`
- `[PROMOTE]`
- `[DEFER]`
- `[IDLE]`
- `[QC]`
- `[AUDIT]`
- `[MILESTONE]`

Rules:

- One line, not a paragraph.
- Always tag.
- Skip no-op chatter.

## Full Example

```markdown
# my-project-coordinator — lane prompt

## 1. Mission
Ship and maintain <project>. Every cycle moves PLAN.md forward, fixes CI,
nurses open PRs, or promotes one inbox finding. Retire when the plan's exit
criteria are met.

## 2. Skills
- /vidux
- /frontend-design

## 3. Read
1. <lane-dir>/my-project-coordinator/memory.md
2. <project-root>/PLAN.md
3. <project-root>/INBOX.md (when present)
4. git fetch && git status --short && git log --oneline -10
5. gh pr list --json number,title,statusCheckRollup

## 4. Gate
- Dirty tree not mine → [QC] concurrent-cycle
- Same task stuck 3+ cycles → [blocked] in `## Decisions`, exit
- Main CI red → fix-first mode

## 5. Assess
1. CI red
2. failing PR
3. mergeable PR
4. resume `[in_progress]`
5. execute next `[pending]`
6. promote inbox finding
7. bounded filler audit, then [IDLE]

## 6. Act
- fresh worktree per code-writing task
- run repo build/test commands literally
- push branch + ready PR by default
- same-runtime subagent dispatch only when the task is clear and bounded

## 7. Authority
- Owns: <project-root>/app/**, PLAN.md, evidence/**, its own memory.md
- Never: secrets, immutable prose, sibling memory files

## 8. Checkpoint
- [2026-04-26T22:10:00Z codex my-project-coordinator] [SHIP] Fixed Task 7 and pushed PR #42. Next: nurse CI.
```

## Failure Modes This Template Prevents

- Missing Mission → lane keeps running after the project is effectively done
- Missing Read order → two cycles start from different assumptions
- Missing Gate → bad cycles burn time before noticing a dirty tree or red CI
- Missing Authority → sibling lanes step on each other
- Missing Checkpoint format → future cycles cannot tell what actually happened
