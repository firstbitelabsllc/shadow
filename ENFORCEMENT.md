# Vidux Enforcement

> Instructions in CLAUDE.md are suggestions. Hooks are enforcement.

A well-written plan means nothing if the agent ignores it. SKILL.md tells the agent what to do. This document describes how to make it _actually do it_ using Claude Code hooks.

## Why Hooks, Not Just Instructions

Instructions in CLAUDE.md or SKILL.md are context. The agent reads them, weighs them against the current prompt, and decides how much to follow. Under token pressure or complex tasks, instructions degrade first. This is the enforcement gap.

Hooks close the gap. They fire at specific lifecycle points and inject guidance (or block execution) regardless of what the agent is "thinking about." Three enforcement levels exist:

| Type | What it does | When to use |
|------|-------------|-------------|
| **prompt** | Injects text into the agent's context before it acts | Guide behavior without blocking. The agent sees the reminder and self-corrects. |
| **command** | Runs a script. Non-zero exit blocks the tool call. | Hard gates: lint, format, destructive command prevention. |
| **agent** | Spawns a sub-agent to evaluate the situation. | Complex judgment calls that need reasoning, not pattern matching. |

Vidux uses **prompt** hooks for plan compliance. Here is why:

- Plan compliance is a judgment call, not a binary check. The agent might be editing a file that isn't literally named in PLAN.md but is clearly implied by the task. A `command` hook would hard-block that — frustrating and wrong.
- Prompt hooks _guide_ the agent back to the plan. They say "hey, this file isn't in the plan — update the plan first if this is intentional." The agent can then choose to update PLAN.md or explain why the edit is covered.
- The goal is unidirectional flow, not a straitjacket. We want the agent to _want_ to follow the plan because the plan is good, and the hook reminds it when it drifts.

---

## Hook 1: PreToolUse — Write/Edit Gate

**Doctrine enforced:** #2 (Unidirectional flow), #1 (Plan is the store)

**Trigger:** Before any `Write` or `Edit` tool call.

**What it does:** Checks if the target file path appears in PLAN.md's Tasks section. If not, injects a reminder to update the plan first.

### Configuration

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX PLAN CHECK: Before writing or editing a file, verify this file is mentioned in (or clearly implied by) a task in PLAN.md. If this file is NOT covered by any task in the plan:\n\n1. STOP — do not proceed with the edit yet.\n2. Update PLAN.md first: add a new task entry (with evidence) that covers this file.\n3. Then return to the edit.\n\nIf the file IS covered by an existing task, proceed normally. The plan is the store. Code is the view. All code changes flow from plan entries."
          }
        ]
      }
    ]
  }
}
```

### What gets injected

Every time the agent calls `Write` or `Edit`, it sees this before the tool executes:

> VIDUX PLAN CHECK: Before writing or editing a file, verify this file is mentioned in (or clearly implied by) a task in PLAN.md. If this file is NOT covered by any task in the plan:
>
> 1. STOP -- do not proceed with the edit yet.
> 2. Update PLAN.md first: add a new task entry (with evidence) that covers this file.
> 3. Then return to the edit.

### Why prompt, not command

A `command` hook here would need a script that parses PLAN.md, extracts file paths from task descriptions, and compares them to the target path. This is brittle:

- Task descriptions often say "implement the boundary shell" not "write `src/APIClientFeature.swift`"
- The script would need fuzzy matching, which means false positives and false negatives
- A blocked edit frustrates the agent and wastes a cycle

A `prompt` hook delegates the judgment to the agent itself. The agent knows what task it is working on. The prompt just reminds it to check. This is the right level of enforcement for a judgment call.

### What good compliance looks like

```
Agent thinks: "I need to edit utils/helpers.ts"
Hook fires: "VIDUX PLAN CHECK: verify this file is in PLAN.md..."
Agent checks: Task 3 says "refactor shared helpers for the new API"
Agent proceeds: utils/helpers.ts is covered by Task 3. Edit continues.
```

```
Agent thinks: "I should also clean up this unrelated test file"
Hook fires: "VIDUX PLAN CHECK: verify this file is in PLAN.md..."
Agent checks: No task mentions this test file. Not implied by current task.
Agent self-corrects: Updates PLAN.md with new task, THEN edits the test file.
```

---

## Hook 2: PostToolUse — Drift Detection

**Doctrine enforced:** #2 (Unidirectional flow), #6 (Process fixes > code fixes)

**Trigger:** After any `Write` or `Edit` tool call completes.

**What it does:** Reminds the agent to check whether the change it just made aligns with the task description in PLAN.md. If the actual change diverged from what the plan specified, the agent should update the plan (UNIFY step from LOOP.md).

### Configuration

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX DRIFT CHECK: You just modified a file. Reconcile planned vs actual:\n\n1. What did the task in PLAN.md say you would do?\n2. What did you actually change?\n3. If they diverge: update PLAN.md to reflect reality. Add a Surprise entry if the divergence was unexpected.\n\nDo NOT silently drift from the plan. The plan must always reflect the true state of the work."
          }
        ]
      }
    ]
  }
}
```

### What gets injected

After every `Write` or `Edit`, the agent sees:

> VIDUX DRIFT CHECK: You just modified a file. Reconcile planned vs actual:
>
> 1. What did the task in PLAN.md say you would do?
> 2. What did you actually change?
> 3. If they diverge: update PLAN.md to reflect reality. Add a Surprise entry if the divergence was unexpected.

### Why this matters

The research is clear: agent code degradation is monotonic (SlopCodeBench, arxiv 2603.24755). Agents don't suddenly break — they drift. Each edit moves slightly further from the spec. By cycle 10, the code bears little resemblance to the plan.

The drift detector catches this per-edit, not per-cycle. It forces the UNIFY step (reconcile planned vs actual) to happen continuously, not just at checkpoint time.

### Why prompt, not command

Same reasoning as Hook 1. Drift is a judgment call. The agent needs to compare the semantic intent of the task ("add error handling to the API client") with the semantic content of the edit (added try/catch blocks). No script can reliably do this comparison. The agent can.

---

## Hook 3: Stop — Checkpoint Enforcement

**Doctrine enforced:** #5 (Design for completion), #2 (Unidirectional flow)

**Trigger:** When the agent session ends (user stops, timeout, or agent completes).

**What it does:** Reminds the agent to write a checkpoint before dying. Every session must leave behind a structured progress entry so the next session can resume.

### Configuration

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX CHECKPOINT: Before this session ends, ensure you have:\n\n1. Updated PLAN.md Progress section with: date, cycle number, what happened, what's next, any blockers.\n2. Checked off any completed tasks in PLAN.md (- [x] with [Done: date]).\n3. Committed all changes with message format: vidux: [summary]\n4. If you have NOT updated the Progress section, do it now. Run vidux-checkpoint.sh or manually update PLAN.md.\n\nThe next session is a different agent. It knows nothing except what's in the files. Leave it a clear trail."
          }
        ]
      }
    ]
  }
}
```

### What gets injected

When the agent is about to stop:

> VIDUX CHECKPOINT: Before this session ends, ensure you have:
>
> 1. Updated PLAN.md Progress section with: date, cycle number, what happened, what's next, any blockers.
> 2. Checked off any completed tasks in PLAN.md.
> 3. Committed all changes.
> 4. If you have NOT updated the Progress section, do it now.
>
> The next session is a different agent. It knows nothing except what's in the files. Leave it a clear trail.

### Why prompt, not command

A `command` hook on Stop could run `vidux-checkpoint.sh` automatically. But:

- The script needs arguments (plan path, task description, summary) that only the agent knows
- An automated checkpoint with wrong arguments is worse than no checkpoint
- The prompt reminds the agent to checkpoint on its own terms, with the right context

However, you CAN pair this prompt hook with a command hook that runs a lightweight check (does `## Progress` have an entry for today?) and prints a warning. The prompt is the primary enforcement; the command is a backup alarm.

### Pairing with a command hook (optional)

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX CHECKPOINT: Before this session ends, ensure you have updated PLAN.md Progress section, checked off completed tasks, and committed all changes. The next session knows nothing except what's in the files."
          },
          {
            "type": "command",
            "command": "bash -c 'PLAN=$(find . -maxdepth 3 -name PLAN.md -path \"*/vidux/*\" 2>/dev/null | head -1); if [ -n \"$PLAN\" ] && ! grep -q \"$(date +%Y-%m-%d)\" \"$PLAN\" 2>/dev/null; then echo \"WARNING: PLAN.md has no progress entry for today. Run vidux-checkpoint.sh before stopping.\"; fi'",
            "async": true
          }
        ]
      }
    ]
  }
}
```

The command hook here is `async: true` — it prints a warning but does not block the stop. It is a belt-and-suspenders pattern: the prompt guides, the command alarms.

---

## Hook 4: SessionStart — Resume Protocol

**Doctrine enforced:** #5 (Design for completion), #1 (Plan is the store)

**Trigger:** When a new session starts.

**What it does:** Injects a directive to read PLAN.md first and find where the previous session left off. This is the "design for completion" principle in action: every session starts by reading the files, not by remembering anything.

### Configuration

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX RESUME: This is a Vidux-managed project. Start by reading PLAN.md:\n\n1. Read PLAN.md — find the Purpose, then go to the Progress section.\n2. Find the last progress entry — that's where the previous session left off.\n3. Check for uncommitted work: run git status and git diff --stat.\n4. If uncommitted work exists from a crashed session, commit it first.\n5. Find the first unchecked task (- [ ]) — that's your job this session.\n6. Follow the Vidux loop: Gather -> Plan -> Execute -> Verify -> Checkpoint.\n\nDo NOT start coding until you know what the plan says. The plan is the store. You are the view."
          }
        ]
      }
    ]
  }
}
```

### What gets injected

When the agent wakes up:

> VIDUX RESUME: This is a Vidux-managed project. Start by reading PLAN.md:
>
> 1. Read PLAN.md -- find the Purpose, then go to the Progress section.
> 2. Find the last progress entry -- that's where the previous session left off.
> 3. Check for uncommitted work: run git status and git diff --stat.
> 4. If uncommitted work exists from a crashed session, commit it first.
> 5. Find the first unchecked task -- that's your job this session.
> 6. Follow the Vidux loop: Gather -> Plan -> Execute -> Verify -> Checkpoint.

### Why this is essential

Without this hook, a fresh session starts with whatever the user's prompt says. The agent has no idea there's a plan, a progress log, or a queue of tasks. It will do what the user says — which might be "implement the feature" — and skip straight to code.

The SessionStart hook ensures the agent's FIRST act is reading the plan. This is the single highest-leverage enforcement in Vidux. If the agent reads the plan, the other hooks are safety nets. If the agent skips the plan, the other hooks are fighting an uphill battle.

### Why prompt, not command

A `command` hook could run `cat PLAN.md` and dump it into context. But:

- PLAN.md might be large. Dumping the whole thing wastes tokens.
- The agent needs to READ it, not just receive it. Reading means finding the relevant section (Progress, next task), not scanning 200 lines of evidence.
- The prompt tells the agent WHAT to read and WHERE to look, which is more effective than a raw dump.

If you want both — the directive AND a quick summary — pair with a command:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX RESUME: This is a Vidux-managed project. Read PLAN.md first. Find the last Progress entry. Check git status for uncommitted work. Find the first unchecked task. Follow the loop: Gather -> Plan -> Execute -> Verify -> Checkpoint."
          },
          {
            "type": "command",
            "command": "bash -c 'PLAN=$(find . -maxdepth 3 -name PLAN.md -path \"*/vidux/*\" 2>/dev/null | head -1); if [ -n \"$PLAN\" ]; then echo \"=== VIDUX PLAN STATUS ===\"; grep -A1 \"^## Progress\" \"$PLAN\" | tail -1; echo \"---\"; grep \"^- \\[ \\]\" \"$PLAN\" | head -3; echo \"($(grep -c \"^- \\[ \\]\" \"$PLAN\") tasks remaining)\"; fi'"
          }
        ]
      }
    ]
  }
}
```

---

## Full Configuration

All four hooks combined in a single `settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX PLAN CHECK: Before writing or editing a file, verify this file is mentioned in (or clearly implied by) a task in PLAN.md. If this file is NOT covered by any task in the plan:\n\n1. STOP — do not proceed with the edit yet.\n2. Update PLAN.md first: add a new task entry (with evidence) that covers this file.\n3. Then return to the edit.\n\nIf the file IS covered by an existing task, proceed normally. The plan is the store. Code is the view. All code changes flow from plan entries."
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX DRIFT CHECK: You just modified a file. Reconcile planned vs actual:\n\n1. What did the task in PLAN.md say you would do?\n2. What did you actually change?\n3. If they diverge: update PLAN.md to reflect reality. Add a Surprise entry if the divergence was unexpected.\n\nDo NOT silently drift from the plan. The plan must always reflect the true state of the work."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX CHECKPOINT: Before this session ends, ensure you have:\n\n1. Updated PLAN.md Progress section with: date, cycle number, what happened, what's next, any blockers.\n2. Checked off any completed tasks in PLAN.md (- [x] with [Done: date]).\n3. Committed all changes with message format: vidux: [summary]\n4. If you have NOT updated the Progress section, do it now. Run vidux-checkpoint.sh or manually update PLAN.md.\n\nThe next session is a different agent. It knows nothing except what's in the files. Leave it a clear trail."
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "VIDUX RESUME: This is a Vidux-managed project. Start by reading PLAN.md:\n\n1. Read PLAN.md — find the Purpose, then go to the Progress section.\n2. Find the last progress entry — that's where the previous session left off.\n3. Check for uncommitted work: run git status and git diff --stat.\n4. If uncommitted work exists from a crashed session, commit it first.\n5. Find the first unchecked task (- [ ]) — that's your job this session.\n6. Follow the Vidux loop: Gather -> Plan -> Execute -> Verify -> Checkpoint.\n\nDo NOT start coding until you know what the plan says. The plan is the store. You are the view."
          }
        ]
      }
    ]
  }
}
```

---

## Design Principles

### Prompt hooks are the right default for plan compliance

Plan compliance is not a binary check. It requires understanding the _intent_ of a task, not just pattern-matching file paths. Prompt hooks delegate this judgment to the agent — the only entity that has enough context to make the call.

Reserve `command` hooks for objective, automatable checks:
- Lint passes? command.
- File exists? command.
- Build succeeds? command.
- "Does this edit align with the plan?" prompt.

### Hooks compose, not compete

Each hook enforces one doctrine principle at one lifecycle point. They do not overlap:

| Hook | Lifecycle | Doctrine | Question it asks |
|------|-----------|----------|-----------------|
| PreToolUse | Before edit | Unidirectional flow | "Is this edit in the plan?" |
| PostToolUse | After edit | Unidirectional flow | "Did this edit match the plan?" |
| Stop | Session end | Design for completion | "Did you checkpoint?" |
| SessionStart | Session begin | Design for completion | "Did you read the plan?" |

Together they form a closed loop: start from the plan, edit per the plan, verify against the plan, checkpoint for the next session, resume from the plan.

### The enforcement gradient

Not all violations are equal. The hooks apply graduated pressure:

1. **SessionStart** — "Read the plan." (Orientation. Gentle.)
2. **PreToolUse** — "Is this in the plan?" (Friction before action. Medium.)
3. **PostToolUse** — "Did you drift?" (Reflection after action. Medium.)
4. **Stop** — "Did you checkpoint?" (Obligation before death. Firm.)

If the agent follows SessionStart properly, it rarely triggers the PreToolUse reminder. If it follows PreToolUse, it rarely triggers drift detection. The hooks are a cascade — each one catches what the previous one missed.

### Enforcement limits

Hooks enforce at the AI tool level (Claude Code, Cursor, Codex). They cannot prevent:
- **Direct git operations** — `git commit`, `git push`, manual file edits bypass all hooks
- **Non-tool agents** — custom scripts, CI systems, and other tools that don't fire hook events
- **In-memory drift** — agents can carry context forward within a session if they choose to ignore hook guidance

For these cases, rely on:
- **Git commit hooks** (`pre-commit-plan-check.sh`) — verifies committed files match plan entries
- **Ledger event logging** — records all work for post-hoc audit, even if hooks were bypassed
- **Code review** — humans catch drift that automated enforcement misses
- **Decision Log** — PLAN.md's Decision Log section prevents cron agents from undoing deliberate choices
