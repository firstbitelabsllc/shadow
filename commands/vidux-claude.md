---
name: vidux-claude
description: "Manage Claude Code automation lanes — CronCreate crons AND Claude Routines (cloud-native, persistent). Create, update, diagnose lanes; fleet ops; migrate CronCreate → Routines."
---

# /vidux-claude

Automation lane management for the vidux ecosystem. Handles both **CronCreate** (session-scoped crons) and **Claude Routines** (cloud-native, persistent automation).

## When to Use

| Primitive | Use when |
|---|---|
| **CronCreate** | Session-scoped experiments, rapid iteration, local-only resources (Xcode, simulators), prototyping a new lane |
| **Routines** | Must survive laptop close, GitHub event triggers, fleet watchers, always-on lanes, PR review pipelines |

## Subcommands

### Create a lane

```
/vidux-claude create <project> <role> [--routine]
```

- Without `--routine`: creates a CronCreate cron in the current session
- With `--routine`: guides you through `/schedule` to create a cloud Routine

Roles: `writer`, `radar`, `coordinator`, `reviewer`, `watcher`

### List lanes

```
/vidux-claude list
```

Shows all active CronCreate crons (via CronList) and Routines (via `/schedule list`).

### Diagnose a lane

```
/vidux-claude diagnose <lane-name>
```

Reads the lane's memory, last 5 ledger entries, and plan state. Reports: SHIPPING / IDLE / BLOCKED / CRASHED / STUCK.

### Migrate CronCreate → Routine

```
/vidux-claude migrate <cron-id>
```

Takes a working CronCreate cron and promotes it to a cloud Routine:
1. Reads the cron's prompt
2. Creates a Routine via `/schedule` with the same prompt
3. Cancels the CronCreate cron (after confirming the Routine is active)

## Routine Configuration

Claude Routines are configured at [claude.ai/code/routines](https://claude.ai/code/routines).

Three trigger types:
- **Scheduled**: min 1h interval, presets (hourly/daily/weekdays/weekly), custom cron via `/schedule update`
- **GitHub events**: PR opened/closed, push, issues, releases, workflow runs, check runs, discussions, merge queue (17 event types). Configured via web UI only.
- **API**: POST to `/fire` endpoint with bearer token. Pass context via `text` field.

Default branch permission: `claude/`-prefixed branches only (matches draft-PR discipline).

## Recipes

See `guides/recipes.md` for 8 ready-to-deploy automation patterns:

| Recipe | Trigger | Role |
|---|---|---|
| Fleet Watcher | Scheduled 2h | Coordinator |
| PR Reviewer | GitHub event (PR) | Reviewer |
| Draft-PR Lifecycle | Scheduled 1h | Tracker |
| Observer Pair | Scheduled (offset) | Observer |
| Deploy Watcher | GitHub event (push) | Verifier |
| Trunk Health | Scheduled 4h | Monitor |
| Skill Refiner | Scheduled 6h | Auditor |
| Self-Improvement | Scheduled 24h | Meta-writer |

## Lane Prompt Structure

Every lane prompt follows the 8-block structure from `guides/fleet-ops.md`:

```
1. MISSION        — one line, user-visible goal
2. SKILLS         — $vidux, $vidux-codex, etc.
3. GATE           — Quick check or SCAN (< 60 sec)
4. AUTHORITY      — read order for plan files
5. CROSS-LANE     — sibling memory + hot-files
6. ROLE BOUNDARY  — what this lane owns
7. EXECUTION      — how to do the work
8. CHECKPOINT     — memory format, lead line
```

Target: 2000-3000 characters. Under 15 lines for the core prompt.

## Hard Rules

- Draft PRs only — never direct-to-main from automation
- Never auto-merge — Leo promotes
- Never fabricate memory files or evidence
- CronCreate for experiments, Routines for production
- All code-writing lanes should delegate to Codex Mode B when task is >10 lines
