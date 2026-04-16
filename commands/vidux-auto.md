---
name: vidux-auto
description: "Automation companion for vidux. Session management, lane operations, delegation modes, fleet ops, PR lifecycle, observer pairs, and platform-specific mechanics for running vidux workers on a schedule."
---

# /vidux-auto

Automation companion for vidux. Covers session management, lane operations, delegation modes, fleet ops, PR lifecycle, and observer pairs. Platform-specific mechanics for running vidux workers on a schedule.

Vidux-auto is the HOW of automation. The core `/vidux` skill is the WHAT (discipline, principles, cycle). Use both together.

Replaces the former `/vidux-claude`, `/vidux-codex`, and `/vidux-fleet` companion skills.

---

## 1. The 24/7 Fleet Operating Model

How lanes persist on disk while sessions cycle. The invariant: lanes survive session restarts because state lives in files, not memory. Hot/cold storage table, session-gc as mandatory infrastructure, and why cloud-based scheduling primitives are rejected (per-account binding, minimum cadence too long, no local file access, no cross-session memory reads).

<!-- SOURCE: vidux-claude L28-75 (fleet model, lane/session diagram, hot/cold table, 5 practice points) -->

---

## 2. Session Management

JSONL growth anatomy, the three GC levels (session prune, archive sweep, full reset), the session-gc lane spec, cycle signal detection, and the current-session-is-never-pruned rule. Measured data: growth rates and compression results.

<!-- SOURCE: vidux-claude L486-563 (session GC, 3 levels, lane spec), L54-61 (hot/cold storage table) -->

---

## 3. Lane Management

Decision tree for how many lanes a project needs. The coordinator pattern (why one coordinator beats N specialists). Observer introduction (details in Section 9). The 6-lane hard cap with measured evidence. Anti-patterns (named specialists, scope bleed). Polish-brake trigger (Principle 4 in practice). Ghost lane detection.

<!-- SOURCE: vidux-claude L117-220 (decision tree, coordinator, observers, cap, anti-patterns, polish-brake) -->

---

## 4. Delegation (Mode A + Mode B)

Two delegation modes for distributing work across agents with different cost/capability profiles.

- **Mode A (Research):** Read-only sandbox, 3-section compressed summary, large token savings.
- **Mode B (Implementation):** Workspace-write sandbox, delegated agent writes code, directing agent reviews diff and ships.

Includes: decision tree (when to delegate), tier math table, invocation flags, temp-file workaround for backticks, the compression contract (Mode A), the 5-block implementation prompt shape (Mode B), and the diff-review checklist.

<!-- SOURCE: vidux-codex L39-97 (Mode A/B diagrams, cost shift table), L136-186 (decision tree, T15 tier math), L207-341 (invocation flags, compression contract, implementation prompt, diff-review checklist) -->

---

## 5. Fleet Operations

Creating, managing, and auditing automation fleets at scale.

- **Slot map:** Visual schedule of all active lanes with cadence and stagger offsets.
- **Prompt templates:** Writer, radar, coordinator, specialist (<=15 lines each).
- **Bimodal quality model:** Quick/deep/stuck-in-middle classification.
- **Validation rubric:** 9 checks (schedule collisions, prompt bloat, doctrine restating, stale automations, bimodal quality, orphan radars, missing coordinator, etc.).
- **Audit scoring:** 9-check rubric, scoring math, report format.
- **Recipe selection heuristics:** Quick-reference table pointing to `guides/recipes.md` for full templates.

> Cross-reference: `guides/recipes.md` for the 11 opinionated automation recipes. `guides/fleet-ops.md` for fleet patterns and gate mechanics.

<!-- SOURCE: vidux-fleet L22-247 (create/fleet/validate, slot map, prompt templates, bimodal quality, hard rules), L392-740 (prescribe/write/audit, recipe selection heuristics, scoring rubric) -->

---

## 6. PR Lifecycle

Mandatory PR triage at the start of every automation cycle. The PR Nurse pattern closes the feedback gap where review comments go unaddressed.

- **Triage:** `gh pr list --state open --author @me` to find automation-created PRs with unaddressed review comments.
- **Nurse responsibilities:** Scan, fix one P1/P2 per cycle, push to PR branch, reply to comment thread, verify CI (remote or local checks for repos without CI), signal READY_FOR_MERGE when all comments resolved.
- **Self-review before push:** Checklist baked into the writer prompt template.

> Cross-reference: `guides/draft-pr-flow.md` for the 5-step draft-PR flow, branch naming, PR body template, and recovery via `gh pr list`.

<!-- SOURCE: vidux-claude L444-448 (mandatory PR triage), NEW (PR Nurse pattern — closes PR #338 gap) -->

---

## 7. Concurrent-Cycle Hazards

Three verified hazards when multiple automation cycles overlap:

1. **lint-staged stash collision** — two cycles run `lint-staged` simultaneously, stash operations corrupt each other.
2. **Branch-switch data loss** — one cycle switches branch while another has uncommitted work.
3. **CI review bot window** — pushing before the previous cycle's CI review completes creates comment races.

Plus the 4-line prevention checklist.

<!-- SOURCE: vidux-claude L456-483 (3 hazards, prevention checklist — all verified bugs) -->

---

## 8. Observer Pairs

Observers are read-only lanes that watch a project for regressions, drift, or missed signals that the primary writer lane is too focused to catch.

- What observers catch (evidence from delegation studies).
- Setup recipe: cadence offset from writer, authority discipline, verdict format.
- When to add one (heuristic): add when a project has >1 active PR or ships >3x/week.

<!-- SOURCE: vidux-codex L396-430 (primary: T8b/T14 evidence, setup recipe, authority), vidux-claude L158-167 (when-to-add heuristic) -->

---

## 9. Worktree Discipline

Per-cycle fresh worktree, symlink dependencies, commit-then-merge flow. The lint-staged branch-hijack gotcha (verified bug: lint-staged rewrites `.git/HEAD` to the worktree's branch). Investigation-only skip rule: read-only cycles may skip worktree creation.

<!-- SOURCE: vidux-claude L420-442 (worktree isolation, symlinks, lint-staged gotcha, skip rule) -->

---

## 10. Prompt File Structure

The 8-block structure for automation prompt files, the <=15 line harness rule, and doctrine avoidance (never restate core vidux principles in prompts — reference the skill instead).

Blocks: Identity, Authority, Cycle, Gate, Act, Push Policy, Checkpoint, Constraints.

Lean templates for each fleet role (writer, radar, coordinator, specialist).

<!-- SOURCE: vidux-claude L230-247 (8-block spec), vidux-fleet L50-107 (writer/radar/coordinator templates) -->

---

## 11. Composition Recipes

Six composition patterns for combining delegation with other tools:

1. **vidux->delegated-agent:** Standard delegation from directing agent to executing agent.
2. **delegated-agent + prompt amplifier:** Amplify vague tasks before delegation.
3. **delegated-agent + research agent:** Package source lookup before implementation.
4. **Agent parallelism:** Fan-out independent subtasks to parallel agents.
5. **Agent wrapper for long crons:** Wrap session-scoped crons in an Agent call for crash recovery.
6. **Review-feedback triage (qa-iterator):** Automated PR review comment triage and fix loop.

<!-- SOURCE: vidux-codex L476-598 (Recipes 1-6, Agent wrapper pattern, qa-iterator) -->

---

## 12. Creating / Updating / Deleting Lanes

Step-by-step workflow for lane lifecycle management.

- **Create:** Discovery scan, slot map check, schedule with stagger, prompt file, memory seed.
- **Cadence table:** Code-writing (30 min), research (60 min), idle-scan (120 min), orchestrator (15 min, RETIRED — use 30 min minimum).
- **Stagger rule:** Fires 8 min apart to avoid worktree contention.
- **Update:** Edit prompt.md on disk, lane picks up changes next cycle.
- **Delete:** Remove the automation config; lane stops at next scheduled fire.

<!-- SOURCE: vidux-claude L282-334 (create/update/delete workflow, cadence table, stagger rule) -->

---

## 13. Memory Files

Append-only checkpoint log per lane. Entry format, reset markers, last-10 visibility rule (agents read the most recent 10 entries, not the full history). Dual-token accounting format for delegation checkpoints.

<!-- SOURCE: vidux-claude L336-362 (entry format, reset markers, visibility rules), vidux-codex L432-439 (dual-token checkpoint format) -->

---

## 14. Lean Fleet Dispatch Rules

Seven prioritized rules for dispatching work across a fleet:

1. Hard cap on concurrent lanes.
2. Max 3-4 parallel agents per wave.
3. Fire-and-forget — don't wait for agent completion.
4. Trust memory.md — don't re-explain context.
5. Don't bloat parent context with child status checks.
6. Absorb duplicate fires — if a lane is already running, skip.
7. Prefer coordinator over multiple specialists.

<!-- SOURCE: vidux-claude L565-577 (7 dispatch rules) -->

---

## 15. Deferred Tool Loading

Platform-specific tools that must be loaded via ToolSearch before use:

- **CronCreate / CronDelete / CronList** — lane lifecycle management.
- **TaskCreate** — task/issue creation from within a cycle.
- **WebFetch** — URL fetching for research cycles.

Always call `ToolSearch` with `select:<tool_name>` before invoking these tools.

<!-- SOURCE: vidux-claude L16-26 (deferred tool prerequisites) -->

---

## 16. External Tool Pairing

When to pair delegation with external research or amplification tools.

- **Research agent pairing:** Package source lookup is significantly cheaper than inline research (measured: 16.5x token savings). Warning: deep research mode causes context overflow on delegation cycles — use quick mode only.
- **Prompt amplifier pairing:** Expand vague tasks into focused specifications before delegating. Most useful when the directing agent receives a one-liner task.

<!-- SOURCE: vidux-codex L343-374 (research pairing, deep-mode warning T14, amplifier pairing) -->

---

## 17. Recommended Agent Config Rules

Three battle-tested rules for agent configuration files (CLAUDE.md, .cursorrules, AGENTS.md, etc.), plus the T1-T4 change classification framework that protects core discipline from churn.

> Cross-reference: `guides/agent-config-rules.md` for the full guide — 3 rules (re-read before edit, re-read after fail, proportional response) + T1-T4 framework (Prompt -> Agent Config -> Companion -> Core).

<!-- SOURCE: guides/agent-config-rules.md (cross-reference, not inlined) -->

---

## 18. Insights Triage Process

After every 10 sessions, review friction findings and classify each as T1-T4. Apply T1 (prompt) and T2 (agent config) immediately. Plan T3 (companion recipe) in PLAN.md. Escalate T4 (core discipline) with a Decision Log entry.

This is a manual process. Build automation only when manual triage proves painful (>15 findings per review).

<!-- SOURCE: Phase 9.4 insights triage process (manual-first) -->

---

## 19. Activation

Activate `/vidux-auto` alongside `/vidux` when:

- Setting up or modifying automation lanes (CronCreate, scheduled agents).
- Diagnosing fleet health, session bloat, or lane contention.
- Delegating work between agents (Mode A/B).
- Running fleet scans, audits, or prescriptions.
- Creating or reviewing draft PRs from automation.
- Pairing a writer lane with an observer.

Do NOT activate for core plan-first work (use `/vidux` alone) or for one-off tasks that don't involve automation infrastructure.

---

## 20. Related Skills

| Skill | Role |
|---|---|
| `/vidux` | Core discipline — principles, cycle, planning |
| `/captain` | Skill registry management |
| `/pilot` | Universal project lead and router |
| `/amp` | Prompt amplifier for vague tasks |
| `/nia` | Research agent for package/doc lookup |
| `/ledger` | Agent activity log for cross-agent coordination |
