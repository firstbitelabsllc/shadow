# Changelog

All notable changes to Vidux are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Vidux uses [Semantic Versioning](https://semver.org/) — minor bumps may tighten doctrine; major bumps change the cycle or `PLAN.md` shape. This file starts at 2.9.0; earlier history lives in git.

---

## [2.16.0] — 2026-04-18

Audit cleanup — catches the stale "Mode A / Mode B" terminology that 2.15.0 missed in tier-3 docs (`references/` + `docs/fleet/`). 26 occurrences renamed to the `research dispatch / implementation dispatch` terminology that 2.15.0 already shipped in `guides/automation.md` and `SKILL.md`. Also fixes a stale deprecation breadcrumb and archives a completed in-flight plan.

### Changed

- **`Mode A / Mode B` → `research dispatch / implementation dispatch`** across 4 files: `references/automation.md` (17 occurrences), `docs/fleet/codex-lifecycle.md` (6), `docs/fleet/codex-setup.md` (1), `commands/vidux-auto.md` (2). This was the remainder left over from 2.15.0's core rename — `guides/automation.md` and `SKILL.md` were already clean, but `references/` still carried the old jargon and the `docs/fleet/` files cross-referenced it. Verified: `grep -c 'Mode A\|Mode B'` returns 0 across all 4 files post-rename.
- **`commands/vidux-auto.md` breadcrumb accuracy fix**. The deprecation breadcrumb claimed `/vidux` has "Part 1 + Part 2 inline" — stale. Per the 2.10.0 structural split, Part 2 moved OUT of SKILL.md to `guides/automation.md`. Breadcrumb now accurately describes the current structure: single entry `/vidux`, Part 1 in SKILL.md, Part 2 in `guides/automation.md`, deep doctrine in `references/automation.md`.

### Moved

- **`PLAN-docs-simplify.md` → `projects/docs-simplify/PLAN.md`**. All 8 tasks `[completed]` since 2026-04-16; plan was cluttering repo root. Preserved via `git mv` (history intact) rather than deleted — the Decision Log entries (platform-agnostic core, TOML-first Codex workflow) still have reference value for future doc-simplification work.

---

## [2.15.0] — 2026-04-18

Doctrine cleanup: plain-English rename of L1/L2 plan nesting, cross-tool delegation removed (not deprecated — removed), vidux.config.json surfaced in core, "markers" jargon dropped. Leo: *"what are markers? … let's kill delegation cross tool concept entirely, 0 deprecation warnings i am sole user."*

### Changed

- **L1/L2 plan-nesting terminology retired.** SKILL.md now calls it "parent plan + child investigation" in plain English. The concept is unchanged (one parent PLAN.md, one child `investigations/<slug>.md`, no deeper nesting) — the jargon was obscuring it. README.md's one-line nesting rule now reads: "One parent plan, one child investigation per compound task — no deeper nesting."
- **Cross-tool delegation removed, not deprecated.** All references to Mode A / Mode B / cross-tool / primary-Claude-+-secondary-Codex scrubbed from SKILL.md, README.md, guides/automation.md. The subagent-dispatch doctrine (which was already same-tool by 2.10.0) is renamed to plain "research dispatch" + "implementation dispatch." No deprecation notices — vidux is a single-user project; backwards-compat shims aren't earning their keep.
- **`[FREEFORM]` / `[METER]` "markers" jargon dropped.** `commands/vidux.md` CHECKPOINT section now calls them "the freeform line" and "the meter bar" — what they literally are. Rule unchanged from 2.13.0 (cycle checkpoints + mission-status replies, not casual chat).

### Added

- **`vidux.config.json` surfaced in core doctrine.** SKILL.md now has a brief "vidux.config.json (where plans live)" section explaining the three plan-store modes (`inline` / `local` / `external`). README.md's new "Status & Config" section shows the same for OSS readers. Previously this only lived in `commands/vidux.md`'s startup flow — SKILL.md readers never encountered it.
- **README.md "Status & Config" section** — documents `scripts/vidux-status.py` usage and `vidux.config.json` minimal schema.

---

## [2.14.0] — 2026-04-18

Concrete script for `/vidux-status`. The slash command is now backed by a real Python script — deterministic, <5s end-to-end, can be called from cron / bash / other agents / CI.

### Added

- **`scripts/vidux-status.py`** (~230 lines, stdlib-only) — read-only scan of every `PLAN.md` under `~/Development/` (or `--root <path>`). Renders the two-bucket board (`🎯 Tied to this chat` + `📋 Other tracked plans`). Sorts by `%` desc then mtime desc. Filters empty + shipped plans by default (`--all` includes them). Flags: `--json` for machine output, `--focus <repo...>` to override cwd-based classification. Tight worktree + nested-vidux-skill-copy filter (skips `*-worktrees/`, `.claude/worktrees/`, `**/ai/skills/vidux/`).

### Usage

```bash
python3 scripts/vidux-status.py
python3 scripts/vidux-status.py --all
python3 scripts/vidux-status.py --focus vidux resplit-web strongyes-web
python3 scripts/vidux-status.py --json | jq '.tied[].percent'
```

---

## [2.13.0] — 2026-04-18

Durable question queue + tightened marker doctrine. The `[DEFER]` tag in vidux-ship-coordinator was a passive name for an active state — replaced with `[ASK-LEO]` pointing at a new `ASK-LEO.md` queue file where questions accumulate instead of re-summarizing in memory.md every cycle. Also tightened 2.12.0's "every response ends with meter+freeform" rule — the markers are for mission-status moments (cycle ends, progress reports), not casual chat. Leo: *"why are u [METER] [FREEForm] everything?"*

### Added

- **`ASK-LEO.md`** at vidux repo root — durable queue of open questions from automation lanes. Each row: title + opened-ts + status + context + Answer line (inline-editable). Lanes log one-line `[ASK-LEO Q<N>]` pointers in their memory.md; the durable state lives in ASK-LEO.md. Seeds with Q1 (Greptile-bypass on vidux repo) + Q2 (PR #27 scope-split).
- **`[ASK-LEO]` + `[ACTED]` tags** in vidux-ship-coordinator prompt §8, replacing `[DEFER]`. Distinct from `[BLOCKED]` (hard technical blocker): `[ASK-LEO]` = armed + ready, waits on one Leo answer.

### Changed

- **Marker rule tightened** in `commands/vidux.md` CHECKPOINT section. Full `[FREEFORM]` + `[METER]` pair applies to cycle checkpoints and mission-status replies. Casual chat, naming/design Q&A, and quick questions skip both. Meter-only is acceptable when you want progress signal without prose.
- **No-noise rule** in vidux-ship prompt §8 now explicitly covers `[ASK-LEO]`: if the prior entry was `[ASK-LEO Q<N>]` and nothing changed, skip the entry entirely. Re-summarizing the question in memory on every cycle is the anti-pattern this release fixes.

---

## [2.12.0] — 2026-04-18

ETAs go mandatory; every cycle ends with a meter. `[ETA: Xh]` tags are now required on `[pending]` and `[in_progress]` tasks — the loose "fill in over time" posture from 2.11 is gone. Every cycle (and every response to the user) now ends with a `[FREEFORM]` line + `[METER]` 20-cell 0–100% bar. Leo: *"vidux plans must have an ETA when planning and every response or automation end needs to express where its at freeform and the 0-100 meter bar, idgaf."*

### Changed

- **`[ETA: Xh]` tag is MANDATORY** on `[pending]` + `[in_progress]` tasks. Dropping a new task into a plan without an ETA is a plan defect — fill it in before checkpoint. Completed + blocked don't need one. 2.11.0's "missing = ∅ AI-hrs not a failure" language softened to "acceptable only on historical tasks pre-2.12.0; new tasks require ETA."
- **Cycle-end format is `[FREEFORM]` + `[METER]`.** Added to `commands/vidux.md` CHECKPOINT section. FREEFORM = 1–3 plain-English sentences on where the work actually sits. METER = 20-cell bar, cell = 5%, mission-wide (not per-task). Coarse on purpose.

### Why

Planning without ETAs lets estimates stay vague forever. Making them mandatory captures the moment of honest guessing; the per-project calibration data (was the `[ETA: 2h]` guess on task N actually 4h?) accumulates naturally and gets tuned later. The FREEFORM + METER cycle-end discipline is for humans reading fleet output — the meter gives Leo a glance-level read without parsing checkpoint prose.

---

## [2.11.0] — 2026-04-18

Cross-repo plan visibility. New `/vidux-status` command renders a two-bucket status board of every PLAN.md on the machine, with progress bars and AI-hour ETAs. PLAN.md Tasks template grows an optional `[ETA: Xh]` tag documenting the new convention.

### Added

- **`/vidux-status` command** (`commands/vidux-status.md`) — read-only scan of every PLAN.md under `~/Development/`, classified into 🎯 Tied to this chat (cwd / session / ledger matches) and 📋 Other tracked plans. Each row renders a 10-cell progress bar + remaining AI-hours + last-Progress timestamp. Never writes, never commits.
- **`[ETA: Xh]` tag convention** on Task lines. Optional. Calibration table in SKILL.md: 0.25h trivial → 8h+ multi-phase (promote to compound). Missing tags render as `∅ AI-hrs` and back-fill over time — not a failure. ETAs are elastic; scope revisions go in `## Decision Log`.

### Changed

- **SKILL.md `## Tasks` template** now shows `[ETA: 0.5h]` and `[ETA: 2h]` on the example rows, with a new paragraph documenting the AI-hour convention.

---

## [2.10.0] — 2026-04-18

Structural refactor. The doctrine machinery shrinks; the recipes layer takes on everything tool-specific, tactical, or customizable. Cross-tool delegation (Claude ↔ Codex) is deprecated — vidux runs single-tool or not at all. Core SKILL.md becomes Part 1 only.

### Added

- **`guides/automation.md`** — the 24/7 fleet operating model, session-gc, lane management, delegation, lane bootstrap. Previously lived as Part 2 of SKILL.md. Now an opt-in guide; load it when you need automation, not to read vidux.
- **`guides/recipes/` directory** with 12 new recipes covering tacit knowledge, delegation patterns, and workflow friction categories from production /insights data:
  - `claude-md-rules.md` — battle-tested CLAUDE.md rules
  - `lane-prompt-patterns.md` — 8-block prompt structure
  - `subagent-delegation.md` — same-tool Mode A / Mode B via `Agent()`
  - `codex-runtime.md` — running vidux natively on Codex Desktop
  - `user-value-triage.md` / `evidence-discipline.md` / `env-var-forensics.md` / `webfetch-fallback.md` / `proactive-surfacing.md` / `lightweight-first.md` / `visual-proof-required.md` — /insights-derived friction recipes
  - `README.md` — recipe index

### Changed

- **SKILL.md shrinks to Part 1 only** (~280 lines, discipline + cycle + PLAN.md + investigations). Part 2 moved to `guides/automation.md`. The Activation section now includes a "Recipes" pointer.
- **Cross-tool delegation deprecated.** Mode A / Mode B were Claude-primary + Codex-secondary cross-tool handoffs. That pattern created context-loss at the egress boundary, prompt-shim fragility, and state-sync surprises. Modern delegation = same-tool subagent dispatch via `Agent()`. The cross-tool era had measured wins (10–110× Mode A / ~5× Mode B) but the reliability cost exceeded the context savings at fleet scale.
- **`/vidux-codex` skill (in `~/Development/ai`) deprecated.** Users who want vidux on Codex: see `guides/recipes/codex-runtime.md`. Users who want cross-tool delegation: pattern is retired.

### Migration

| Old shape | New shape |
|---|---|
| `SKILL.md` Part 2 | `guides/automation.md` |
| Mode A / Mode B (Claude→Codex) | `guides/recipes/subagent-delegation.md` (same-tool via `Agent()`) |
| Codex shim registration (inline in SKILL.md / vidux-codex skill) | `guides/recipes/codex-runtime.md` |
| `/vidux-codex` skill | Deprecated — see `codex-runtime.md` recipe |

### Versioning note

This is a minor bump (2.9.0 → 2.10.0) because:

- The five principles, the cycle, and the required PLAN.md sections are unchanged
- Existing SKILL.md readers get redirected, not broken
- Lane prompts that reference Mode A / Mode B still work (the pattern name is preserved; only the cross-tool variant is deprecated)

Contract tests pass with the same baseline (133 pass / 3 pre-existing failures).

---

## [2.9.0] — 2026-04-17

Doctrine patch with two aims: (1) kill the fleet-scale failure mode where agents picked cheap meta-tasks over real bug fixes, and (2) shift the discipline toward **autonomous adaptive work** — fewer human-gated checkpoints, fewer required sections, fewer ceremonies the agent has to observe. The result is a smaller doctrine that trusts the agent more.

**Net effect on the code base:** substantial net deletion across SKILL.md, DOCTRINE.md, LOOP.md, docs/, guides/, references/, and commands/. The discipline gets smaller, not bigger.

### Added

- **`observed` is now a first-class evidence type.** User-observed behavior is citable evidence of equal standing to `codebase grep`, `GitHub PR`, or `design doc`. This closes the ingest path for bugs a human sees in the running app.

  ```markdown
  ## Evidence
  - [Source: observed] "flicker on first render after launch" (v2.4.1)
  - [Source: observed] "Remove button silently no-ops during active session"
  ```

  Previously the allowed evidence sources were all document-oriented. If no one had written the bug into a PR, a design doc, or a chat log, the bug had no way to enter the plan. The doctrine now treats the running app as a valid source.

### Changed — Core Rule

- **Progress is code change.** A PR that only touches `PLAN.md`, `investigations/`, `evidence/`, or `INBOX.md` without a source-code change is bookkeeping, not progress. Bundle plan updates into the code PR that ships the fix, or keep notes local until a fix is ready.

  The following shapes are now prohibited as standalone PRs:
  - `flip row to [completed]`
  - `reconcile Phase N`
  - `audit already-delivered`
  - `investigation closeout` without a code fix

  **Why:** at fleet scale, the cheap tasks produce mergeable PRs faster than real bug fixes. Lanes that optimize for merge count will consistently pick the cheap path. This rule takes the cheap path off the table — when a lane needs a task, the only moves left are actual code changes.

- **Investigation-only cycles no longer commit.** Previously the doctrine said *"the cycle is investigation only — no code"* in several places, permitting a commit of only the investigation file. The rule is now inverted: if a cycle produces no code, it produces no commit and no PR. The investigation file stays on disk for the next cycle to pick up, and ships in the same PR as the fix.

  Before:
  > If the Fix Spec is missing, the cycle is investigation only -- no code.

  After:
  > Investigation notes live locally in the working tree until the fix ships — they are not a separate deliverable.

- **LOOP.md checkpoint rule inverted.** *"Every cycle MUST produce a checkpoint commit, even if no code changed"* → *"A cycle produces a commit only when code changed."*

- **24/7 lane count recommendation simplified.** Was 3–7 lanes per repo (coordinator + optional observer + session-gc). Now 2–4 lanes per repo (coordinator + session-gc). The observer slot is gone.

### Changed — Autonomous Adaptive Doctrine

This section collects the cuts and small rewrites that together shift vidux toward agents that adapt on their own rather than pausing for human-gated ceremony. Every change in this section either deletes a rule outright or replaces it with a more permissive, agent-owned equivalent.

- **Queue re-sort is now agent-owned.** The old "No reordering mid-cycle — to change priority, update the plan with a Decision Log entry" rule is gone. The agent re-sorts the queue when new `[Source: observed]` evidence, a Decision Log entry, or a failing deploy changes priority. The reorder is noted in the next Progress entry, no permission required.

- **Queue selection is impact-weighted, not strict FIFO.** Old: *"[pending] tasks run top-to-bottom — the first eligible task wins."* New: *"Pick the highest-impact unblocked task."* FIFO remains the default; impact-weighting kicks in when the priority signal is obvious.

- **`[P]` parallel marker removed from queue order.** The `[P] tasks may run in parallel — up to 4 concurrent agents, one point guard` rule is gone. Parallel research fan-out still happens where it helps (Mode A delegation, investigation agents), just not via a static marker embedded in every task description.

- **3× stuck rule no longer requires a human.** Old: *"If the same task appears in 3+ Progress entries while still `[in_progress]`, mark it `[blocked]` with a Decision Log entry. Only a human can unblock it."* New: *"3× stuck → force a surface switch to the next unblocked task. Mark the stuck one `[blocked]` with a one-line Decision Log entry. No human hand-off required; next cycle either finds new evidence that unblocks it — via observed signal, new PR comment, or queue re-sort — or the task stays blocked until replaced."* The brake still prevents forever-loops; the human no longer sits in the critical path.

- **Status FSM — `blocked` is now terminal.** The old FSM had a `blocked → pending` reverse transition, implying blocked tasks would automatically revive. Blocked is now terminal; a new task replaces a blocked one (with a Decision Log entry explaining the direction change).

- **L3 investigation escape hatch removed.** The old doctrine allowed "L3 is allowed only when an investigation reveals a nested bug that itself needs investigation -- this is rare." Removed entirely. Max two levels (L1 plan, L2 investigation) is firm. If a surface needs deeper decomposition, split it into separate L1 plans.

- **Push authorization compressed to one rule.** Replaced the three-tier ladder (Draft PRs / Direct-to-main / Destructive) with a single sentence: *"Draft PRs are always safe. Direct-to-main or destructive operations (force push, branch delete, `git reset --hard`) require explicit authorization."* Lane prompts that say "NEVER push" without qualification still allow draft PRs; parking on a safe draft-PR push wastes cycles.

- **Garbage collection thresholds removed.** The old aspirational rules (*"Archive when PLAN.md exceeds 200 lines, prune worktrees older than 24h, rotate Decision Log older than 180 days, clean INBOX entries"*) are gone. Replaced with: *"Archive completed tasks when the plan feels heavy — the agent decides, no fixed threshold."* Nobody ran the thresholds; they were ceremony.

- **"Every agent is a worker" folded into the ACT step.** The standalone section is gone. Its instruction now lives inline in the cycle: *"Empty queue? Scan INBOX, owned paths, git log, blocked tasks. Anything found becomes [pending] and runs this cycle. Nothing found? Checkpoint and exit."*

- **Principle 4 addendum — evidence-driven re-sort.** One new line: *"If evidence changes mid-cycle, the queue re-sorts. Observed user behavior, a failing deploy, a new PR comment — any of these can reorder what's next. You don't need permission to reorder. Note the reorder in the next Progress entry so future agents see the why."*

### Changed — PLAN.md Template

- **`## Open Questions` section is now optional.** It is no longer listed in the required PLAN.md template and the contract test (`tests/test_vidux_contracts.py` `REQUIRED_PLAN_SECTIONS`) has been loosened to drop it. Plans that already have the section continue to work. New plans can skip it. Promote a question to a `[pending]` research task, or note it on the blocking task as `[Blocker: need evidence for X]` — a dedicated section is no longer required.

- **`## Surprises` section is now optional.** Same treatment. Unexpected findings during execution go into the Progress entry for that cycle, or promote to a new task if actionable. The Decision Log captures intentional pivots. A dedicated Surprises section duplicates both.

- **Status FSM in the template** updated to show `blocked` as terminal (no `blocked → pending` reverse transition).

The contract test `test_plan_has_required_sections` now requires 6 sections: `Purpose`, `Evidence`, `Constraints`, `Decisions`, `Tasks`, `Progress`. Down from 8. Existing plans with Open Questions + Surprises sections remain valid.

### Deprecated — Observer Lane Pattern

Observer lanes (read-only audit lanes that watch a writer each cycle) are deprecated as an orchestration smell. They add memory.md files, cross-lane reads, and cycle offsets without catching bugs that the writer could not already see in its own logs. Drift belongs upstream — fix the writer's prompt or the doctrine producing drift. Don't pay for a second scheduled lane to report it back.

Deprecation targets:

| Location | Change |
|---|---|
| `references/automation.md` Section 8 (Observer Pairs) | Full section collapsed to a 3-line deprecation notice |
| `references/automation.md` Section 3 "The observer" subsection | Rewritten as "Observer lanes are deprecated" |
| `references/automation.md` Section 8.5 step 4 (Cross-Fleet Coordination) | Observer-as-fleet-health step removed |
| `guides/recipes.md` Recipe 1 (Fleet Watcher) | Marked DEPRECATED with blockquote warning |
| `guides/recipes.md` Recipe 4 (Observer Pair) | Marked DEPRECATED with blockquote warning |
| `docs/index.md` Fleet Intelligence feature card | "Observer pairs" removed from description |

**Alternatives if you need what observers were doing:**

- **Independent eyes on a specific concern.** Run a one-shot audit by hand. A human reading the writer's recent memory.md tail for 5 minutes catches more than a scheduled observer running every cycle.
- **Fleet health tracking.** Put health checks in the writer's own cycle — it already reads its state each fire. `session-gc` already tracks disk pressure across sessions.
- **Prompt drift detection.** If a writer keeps producing the wrong thing, fix the writer's prompt. The observer catching the drift does not fix the underlying bug.

Existing observer lanes are not auto-migrated. They will continue to work. Consider winding them down at your next maintenance window.

### Migration Guide

If your lane prompts, `CLAUDE.md`, `AGENTS.md`, or automation README files reference the old doctrine phrasings, replace them:

| Old phrasing | New phrasing |
|---|---|
| `investigation only — no code` | `no PR until the fix ships` |
| `no code this cycle` | `no commit until the fix ships` |
| `Every cycle MUST produce a checkpoint commit` | `A cycle produces a commit only when code changed` |
| `observer pair`, `fleet watcher` | (deprecated — see alternatives above) |
| `preemptive observer` | (deprecated) |
| `No reordering mid-cycle` | `Re-sort the queue when observed evidence changes priority; note in Progress` |
| `first eligible [pending] wins` | `Pick the highest-impact unblocked task` |
| `[P] tasks may run in parallel` | (removed from queue order; parallel fan-out still valid for research) |
| `L3 is allowed only when...` | (removed — max two levels, split into separate L1 plans) |
| `Only a human can unblock it` (3× stuck rule) | `Force a surface switch; next cycle finds new evidence or task stays blocked` |
| `blocked → pending` FSM transition | (removed — blocked is terminal, replaced by a new task) |
| `Archive when PLAN.md exceeds 200 lines` | `Archive when the plan feels heavy — agent decides` |
| `## Open Questions` required section | Optional — promote to `[pending]` task or `[Blocker: ...]` annotation |
| `## Surprises` required section | Optional — note in Progress entry |

No change to:

- The five principles (1–5 all preserved; Principle 4 gained a one-line addendum on queue re-sort).
- The cycle (READ → ASSESS → ACT → VERIFY → CHECKPOINT).
- Required PLAN.md sections: `Purpose`, `Evidence`, `Constraints`, `Decisions`, `Tasks`, `Progress`. (Open Questions + Surprises moved to optional.)
- `INBOX.md` ingest pattern.
- The agent ledger (`.agent-ledger/activity.jsonl`).
- Planning and nested planning (compound tasks, `[Investigation: ...]` markers, sub-plans).
- The automation harness (session management, cron scheduling, session-gc).
- Delegation modes (Mode A research / Mode B implementation).
- Draft-PR flow.
- Evidence file naming and format (aside from the new `observed` source type).
- The 3× stuck-loop detection threshold itself (still 3 consecutive Progress entries) — only the *response* changed from "mark blocked, human unblocks" to "force surface switch, no human required."

### Contract Tests

`tests/test_vidux_contracts.py` passes at the same level as before: 133 pass / 3 pre-existing failures, none introduced by this release. `REQUIRED_PLAN_SECTIONS` was loosened to drop `Open Questions` and `Surprises` (now 6 required sections down from 8) — this is a contract weakening, not a contract break. All plans that passed the old contract still pass the new one.

---

## Versioning Policy

- **Patch (2.9.0 → 2.9.1):** typo fixes, doc clarifications, additional examples.
- **Minor (2.9.0 → 2.10.0):** tightening rules, adding evidence types, deprecating patterns. No breaking changes to the cycle or `PLAN.md` template.
- **Major (2.9.0 → 3.0.0):** changes to the cycle shape, the five principles, or the required `PLAN.md` sections. Contract tests would change.

This release is minor because: new evidence type adds a valid shape (backward compatible); "no metadata-only PR" tightens but doesn't break existing valid PRs; observer deprecation does not remove the capability to run a read-only lane, only the official pattern recommendation.
