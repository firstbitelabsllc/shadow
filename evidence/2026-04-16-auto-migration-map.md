# vidux-auto Migration Map

Generated 2026-04-16 for Phase 8.0. Classifies every section of the three companion
skills as CORE / AUTO / PERSONAL / DEAD / OVERLAP to guide the merge into `/vidux-auto`.

Cross-reference files used:
- `vidux/SKILL.md` (297 lines) — core discipline
- `vidux/guides/agent-config-rules.md` (101 lines) — T1-T4 framework + 3 rules
- `vidux/guides/recipes.md` (517+ lines) — 8 opinionated recipes

---

## vidux-claude/SKILL.md (619 lines)

| Lines | Section | Classification | Notes |
|---|---|---|---|
| 1-5 | Frontmatter (name, description) | DEAD | Replaced by vidux-auto frontmatter |
| 7-14 | Intro + Claude-vs-Codex framing | AUTO+PERSONAL | Migrate the "in-session cron loop" definition. Strip L13 "Leo's fleet is migrating Codex" |
| 16-26 | Tool prerequisites (deferred tools, ToolSearch) | AUTO | Claude Code-specific but operational. Migrate as "Deferred Tool Loading" section |
| 28-75 | The 24/7 Fleet Operating Model | AUTO+PERSONAL | Core fleet model. Strip L67 "Leo rotates through 4 accounts", L154 "Leo switches accounts", L175 "Leo needs to scan N memory.md files". Keep the lane-vs-session diagram, hot/cold storage table, invariant description |
| 34-40 | Lane/session ASCII diagram | AUTO | Good visual — keep verbatim |
| 41-52 | What this means in practice (5 points) | AUTO | Session cycling, session-gc mandate, lane cap, cross-session handoff. All operational |
| 54-61 | Hot vs cold storage table | AUTO | Migrate as-is |
| 63-74 | Why not cloud Routines? | DEAD | Superseded by Decision Log 2026-04-15: "delete Routines we dont need it anymore its cloudbase." The rejection reasoning is still valid but the comparison framing assumes Routines are an option. Trim to a 2-sentence note: "Cloud Routines are rejected for this fleet (per-account binding, 1h min cadence, no local file access, no memory.md cross-reads)" |
| 77-87 | Subcommands | DEAD | These are vidux-claude specific subcommands (`/vidux-claude create`, etc.). vidux-auto gets its own subcommand list |
| 89-114 | How a lane works (prompt.md + memory.md + CronCreate) | AUTO | Core lane mechanics. Migrate |
| 117-178 | How many lanes per assignment (decision tree + 6-lane cap) | AUTO+PERSONAL | The decision tree, coordinator pattern, anti-patterns are all operational. Strip L154 "Leo switches accounts", L175-176 "Leo needs to scan / Leo has 4". Keep the measured data (L173-174 worktree contention, JSONL math) |
| 143-156 | The coordinator pattern (why one coordinator beats N specialists) | AUTO | Valuable. Keep all 5 bullets |
| 158-167 | The observer (exception to "fewer lanes") | OVERLAP | Also covered in vidux-codex L396-430. vidux-claude version is shorter but references vidux-codex for full contract. Merge: use vidux-codex's richer version as primary, keep vidux-claude's "when to add one" heuristic |
| 169-178 | Why the hard cap at 6 (measured data) | AUTO | Keep — verified measurements. Strip L175 "Leo" |
| 180-205 | Anti-patterns + minimum lanes | AUTO | Keep verbatim |
| 187-196 | Concrete example: Leo's active fleet (2026-04) | PERSONAL | Table names `leojkwan-coordinator`, `strongyes-coordinator`, `qa-iterator`. Genericize to `<project-a>-coordinator`, `<project-b>-coordinator`, `<burst-lane>` |
| 208-219 | Polish-brake trigger (Principle 4 in practice) | AUTO | Operationalizes core Principle 4. Migrate. Strip L216 "leojkwan" |
| 221-228 | Why prompt file on disk | AUTO | Migrate. Strip L227 "A/B against Codex" paragraph (Codex is legacy) |
| 230-247 | Standard prompt file structure (8 blocks) | OVERLAP | Also in vidux-fleet L52-70 (writer template), L72-89 (radar template), L91-107 (coordinator template). vidux-claude's 8-block breakdown is the structural spec; vidux-fleet's templates are the implementations. Keep both: 8-block spec from claude, templates from fleet |
| 249-280 | Codex delegation inside an Act block (Framing B lanes) | OVERLAP | Fully covered in vidux-codex L39-97 (Mode A/B with more detail). Drop this section, reference vidux-codex's version during migration |
| 282-313 | Creating a lane | AUTO | Step-by-step CronCreate workflow. Migrate. The cadence table (L301-308) is valuable operational data |
| 308 | 15-min cadence RETIRED | AUTO | Key operational finding — keep |
| 310-311 | Stagger fires 8 min apart | AUTO | Keep |
| 315-326 | Updating a lane | AUTO | Migrate |
| 328-334 | Deleting a lane | AUTO | Migrate |
| 336-362 | Memory files — append-only checkpoint log | AUTO | Entry format, reset markers, visibility rules. Migrate |
| 364-404 | Fleet operations (fleet scan + legacy Codex) | AUTO+DEAD | L364-389 Claude lane scan is AUTO. L391-404 Legacy Codex scan is DEAD (Codex fleet deprecated per Phase 6.3.1) |
| 406-418 | A/B testing with /codex | DEAD | Codex fleet deprecated. Drop |
| 420-442 | Worktree discipline | AUTO+PERSONAL | L427 `strongyes-web` example path — genericize. L435 "explicit Leo authorization" — genericize to "explicit human authorization". Keep the lint-staged branch-hijack gotcha (L439-442) — verified bug |
| 444-448 | Open PR triage (mandatory first action) | AUTO | This is the pattern that became PR Nurse. Migrate as foundation for PR lifecycle section |
| 450-453 | Live state from PLAN.md (anti-pattern) | CORE | Already in vidux core: "Plan first, code second" + "After any interruption, re-read PLAN.md from disk." Keep as a 1-line reference, don't duplicate |
| 456-483 | Concurrent-cycle hazards | AUTO | All three hazards (lint-staged stash, branch-switch, CI review window) + prevention checklist. Migrate verbatim — verified bugs |
| 486-563 | Session GC (the 24/7 enabler) | AUTO+PERSONAL | L490 "5-10MB/hour with an active fleet" — keep. L522 measured results "1.2GB -> 557MB" — keep. L534 "Leo reads the signal" — genericize to "the human reads". L542-557 session-gc lane spec — migrate. L559-561 "don't create plan-gc lane" — migrate |
| 565-577 | Lean fleet dispatch | AUTO+PERSONAL | L565 "Leo direct 2026-04-15" — strip attribution. L570-571 "Leo has 4" — genericize. All 7 rules are operational — migrate |
| 579-589 | Integration with /vidux | CORE | Already implied by core's "Automation is platform-specific" section. Keep as 2-line cross-reference in vidux-auto intro, don't duplicate |
| 591-605 | Activation | DEAD | vidux-auto gets its own activation section |
| 607-619 | Related Skills table | DEAD | vidux-auto replaces this table with its own. Many entries (vidux-codex, vidux-fleet, vidux-claude) will no longer exist as separate skills |

---

## vidux-codex/SKILL.md (626 lines)

| Lines | Section | Classification | Notes |
|---|---|---|---|
| 1-4 | Frontmatter | DEAD | Replaced by vidux-auto frontmatter |
| 6-11 | Intro (Claude directs, Codex executes) | AUTO | Core delegation concept. Migrate. Strip "This is NOT a separate skill from /vidux" — that framing is about the old multi-skill model |
| 12-37 | Scheduling primitive: CronCreate + session-gc (opinionated) | OVERLAP | 80% overlap with vidux-claude L28-75 (24/7 Fleet Model). The vidux-codex version is a condensed summary ("Quick summary"). Drop — vidux-claude's full version is better |
| 39-97 | The two delegation modes (Mode A + Mode B) | AUTO | This is THE canonical delegation reference. Migrate verbatim. The ASCII flow diagrams (L45-58 Mode A, L64-79 Mode B), cost shift table (L83-96) — all essential |
| 98-134 | Why this exists (token bottleneck) + 4 framings table | AUTO+PERSONAL | L130 "Leo's actual constraint" — genericize to "the common constraint". L106-109 "Frankenstein experiment" paths — genericize. The 4 framings table (L123-128) is universally useful. The tier math (L180-186) is key evidence. Keep all, scrub personal refs |
| 136-176 | When to delegate (decision tree) | AUTO | The full decision tree is the operational heart of delegation. Migrate verbatim |
| 178-186 | T15 tier math table | AUTO | Hard evidence. Keep verbatim |
| 188-205 | The cycle (READ/ASSESS/RESEARCH/ACT/VERIFY/CHECKPOINT) | OVERLAP | The cycle itself is CORE (vidux SKILL.md L50-60). The RESEARCH step addition is AUTO. Migrate only the delta: "Only the RESEARCH step is new" + the research sub-steps |
| 207-274 | Invocation flags (Mode A + Mode B commands) | AUTO | Critical operational detail. Keep the `codex exec` command templates, flag semantics, temp-file workaround for backticks (L256-274). All verified |
| 276-289 | Mode A — The compression contract | AUTO | Mandatory prompt template. Migrate verbatim |
| 291-341 | Mode B — Implementation prompt shape + diff-review checklist | AUTO | The 5-block spec (L296-302), worked example (L304-329), diff-review checklist (L333-341). All essential. Migrate |
| 343-365 | Pairing with /nia | AUTO | Decision tree for nia vs codex. L354-365 "NEVER use nia_research(mode='deep')" warning is load-bearing. Migrate |
| 367-374 | Composing with /amp | AUTO | When to amplify prompts before delegation. Migrate |
| 376-382 | Authority paths | CORE | Standard vidux path convention. Already in core PLAN.md template. Skip |
| 384-394 | Execution rules (9 rules) | AUTO | All 9 are operational. Migrate |
| 396-430 | Pair with an observer lane | OVERLAP | Also referenced in vidux-claude L158-167 and vidux-fleet L224-250 (Recipe 4). vidux-codex has the most complete version: T8b/T14 evidence, setup recipe (L418-430), why Codex for observers. Use this as the primary observer reference. Drop the claude+fleet versions. Strip L412 "Leo's fleet" |
| 432-439 | Checkpoint format | AUTO | Dual-token accounting format. Migrate |
| 441-455 | Activation | DEAD | vidux-auto gets its own activation section |
| 457-468 | Relationship to /vidux (table) | CORE | Already stated in core: "Automation is platform-specific." Skip |
| 469-474 | Delegation never spawns a new plan store | CORE | This IS core vidux principle ("Every project has exactly ONE PLAN.md" — SKILL.md L87). Skip — already in core |
| 476-608 | Composition Recipes (Recipes 1-6 + why skills-as-commands) | AUTO | Recipe 1 (vidux->codex delegation), Recipe 2 (codex+amp), Recipe 3 (codex+nia), Recipe 4 (Agent parallelism), Recipe 5 (Agent wrapper for long crons), Recipe 6 (review-feedback triage / qa-iterator). All operational patterns. Recipe 5 (L531-556) is especially important for autonomous crons. Recipe 6 (L558-598) includes the qa-iterator pattern. Migrate all. Strip L560 "leojkwan fleet" reference |
| 600-608 | Why skills-as-commands works | DEAD | Claude Code version-specific implementation detail (v2.1.1). Drop — this is meta about skills framework, not vidux |
| 610-622 | Related Skills table | DEAD | vidux-auto replaces this |
| 624-626 | Experiment references | AUTO | Keep as a 2-line note: "Numbered experiments (T1-T22) come from the Phase 1/2 delegation study. Raw data at the experiment repo" |

---

## vidux-fleet/vidux-fleet.md (753 lines)

This file is a concatenation of two merged skills: `vidux-loop` (L1-247) and `vidux-recipes` (L248-753).

### vidux-loop section (L1-247)

| Lines | Section | Classification | Notes |
|---|---|---|---|
| 1-4 | Frontmatter (vidux-fleet) | DEAD | Replaced by vidux-auto frontmatter |
| 6-10 | Intro + primitive priority note | AUTO+DEAD | L6 "# /vidux-loop" header — dead (merged into vidux-fleet, now merging into vidux-auto). L9-10 primitive priority note references `/schedule` and Claude Routines — DEAD per Decision Log 2026-04-15 (Routines stripped). Keep the concept of "fleet builder for recurring loops" |
| 12-20 | Subcommands (create/fleet/validate/coordinator) | AUTO | Migrate as vidux-auto subcommands, adapted |
| 22-48 | create — steps 1-4 (discover, slot map, schedule) | AUTO | Slot map logic, lowest-density slot finding, cadence defaults. Migrate. L37-39 discovery scan paths: strip "Claude Routines: `/schedule list`" (DEAD per Routines decision). Keep CronCreate + Codex legacy scan |
| 50-107 | Prompt templates (writer/radar/coordinator) | AUTO | The three lean prompt templates are core fleet patterns. Migrate |
| 109-156 | Generate automation config (Routine/CronCreate/Codex) | AUTO+DEAD | L111-121 Claude Routine config: DEAD (stripped per Decision Log). L123-129 CronCreate lane: AUTO. L131-155 Codex automation.toml: DEAD (legacy, do not create new) |
| 158-160 | Update fleet registry + checkpoint | AUTO | Migrate |
| 162-193 | fleet subcommand (slot map display) | AUTO | Slot map format, bimodal quality display. Migrate |
| 195-220 | validate subcommand (7 checks) | AUTO | Schedule collisions, prompt bloat, doctrine restating, stale automations, bimodal quality, orphan radars, missing coordinator. All operational. Migrate |
| 222-235 | Bimodal Quality Model | AUTO | Quick/deep/stuck-in-middle classification. Migrate |
| 237-247 | Hard Rules (7 rules) | AUTO | 15-line limit, no doctrine restating, "keep working", max 3 per minute, coordinator required. Migrate |

### vidux-recipes section (L248-753)

| Lines | Section | Classification | Notes |
|---|---|---|---|
| 248-253 | Frontmatter (vidux-recipes) | DEAD | Already merged into vidux-fleet, now merging into vidux-auto |
| 255-263 | Intro + stage system | AUTO | Stage indicators are useful for structured output. Migrate |
| 265-274 | Subcommands (list/prescribe/write/audit) | AUTO | Migrate as vidux-auto subcommands |
| 278-389 | list subcommand + Recipe Catalog (6 recipes) | OVERLAP+PERSONAL | The 6 recipes (Solo Writer, Writer+Radar, Writer+2Radars+Coordinator, Multi-Repo Fleet, Maintenance Mode, Deep Work Mode) overlap significantly with `guides/recipes.md` which has 8 more detailed recipes. L355 "Beacon/Acme 2.0-style" — generic (keep). L369 "Leo is heads-down" — PERSONAL, genericize to "the operator is heads-down". Decision: keep the recipe catalog as a quick-reference table in vidux-auto, point to guides/recipes.md for full templates |
| 379-389 | Recipe Selection Heuristics table | AUTO | Compact selection guide. Migrate |
| 392-477 | prescribe subcommand (full algorithm) | AUTO+PERSONAL | L436 "Leo says 'deep work'" — genericize. The signal parsing (L414-419), decision tree (L434-441), fleet comparison (L443-446) are all operational. Migrate |
| 480-645 | write subcommand (harness generation) | AUTO+PERSONAL | L489-491 `--target routine` flag — DEAD (Routines stripped), default should become `claude-lane`. Writer harness template (L515-530) — keep. Radar harness template (L534-553) — keep. Coordinator harness template (L556-570) — keep. Specialist harness template (L573-592) — keep. L603-609 `--target routine` execution path — DEAD. L607-609 `--target codex-legacy` — DEAD (legacy). Keep only `--target claude-lane` path |
| 647-740 | audit subcommand (scoring rubric) | AUTO | 9-check rubric (L671-681), scoring math (L683-687), report format (L689-738). Migrate |
| 742-753 | Hard Rules (8 rules) | AUTO | Deterministic recipes, read-only prescribe/audit, one file per write, 15-line harness limit, new doctrine compliance, no restating, stage indicators, command file length exemption. Migrate |

---

## Proposed vidux-auto TOC

Based on the classifications above, here is the proposed section structure for `/vidux-auto`:

```
# /vidux-auto

## 1. What This Is
   Brief: the single automation companion to vidux core.
   Replaces: /vidux-claude, /vidux-codex, /vidux-fleet.
   Cross-ref: vidux SKILL.md for the core discipline.

## 2. The 24/7 Fleet Operating Model
   Source: vidux-claude L28-75
   Content: lanes persist on disk, sessions cycle, session-gc mandatory,
   hot/cold storage table, why not cloud Routines (2-sentence note).

## 3. Session Management
   Source: vidux-claude L486-563 (session GC), L54-61 (hot/cold)
   Content: JSONL growth anatomy, 3 GC levels, session-gc lane spec,
   cycle signal, current-session-is-never-pruned rule.

## 4. Lane Management
   Source: vidux-claude L117-220
   Content: decision tree (how many lanes), coordinator pattern (why 1 beats N),
   observer intro (with pointer to Section 9), 6-lane hard cap (measured),
   anti-patterns, polish-brake trigger, ghost lane detection.

## 5. Delegation (Mode A + Mode B)
   Source: vidux-codex L39-97, L136-186, L207-341
   Content: Mode A (research, compression contract), Mode B (implementation,
   5-block prompt, diff-review checklist), decision tree (when to delegate),
   T15 tier table, invocation flags, temp-file workaround.

## 6. Fleet Operations
   Source: vidux-fleet L22-247 (create/fleet/validate), L392-740 (prescribe/write/audit)
   Content: slot map, stagger rules, prompt templates (writer/radar/coordinator/specialist),
   bimodal quality model, validation rubric (9 checks), audit scoring,
   recipe selection heuristics (quick-ref table -> guides/recipes.md for full).

## 7. PR Lifecycle (NEW — closes PR #338 gap)
   Source: vidux-claude L444-448 (PR triage), NEW PR Nurse pattern
   Content: mandatory PR triage at cycle start, PR Nurse responsibilities
   (scan, fix one P1/P2, push, verify, READY_FOR_MERGE signal), local CI
   for repos without remote CI.

## 8. Concurrent-Cycle Hazards
   Source: vidux-claude L456-483
   Content: lint-staged stash collision, branch-switch data loss,
   CI review bot window, 4-line prevention checklist.

## 9. Observer Pairs
   Source: vidux-codex L396-430 (primary), vidux-claude L158-167 (heuristic)
   Content: what observers catch (T8b/T14 evidence), setup recipe,
   cadence offset, authority discipline, verdict format.

## 10. Worktree Discipline
    Source: vidux-claude L420-442
    Content: per-cycle fresh worktree, symlink deps, commit-then-merge,
    lint-staged branch-hijack gotcha, investigation-only skip rule.

## 11. Prompt File Structure
    Source: vidux-claude L230-247 (8-block spec), vidux-fleet L50-107 (templates)
    Content: 8-block structure, <=15 line harness rule, doctrine avoidance.

## 12. Composition Recipes
    Source: vidux-codex L476-598
    Content: 6 recipes (vidux->codex, codex+amp, codex+nia, Agent parallelism,
    Agent wrapper for long crons, review-feedback triage/qa-iterator).

## 13. Creating / Updating / Deleting Lanes
    Source: vidux-claude L282-334
    Content: step-by-step CronCreate workflow, cadence table (code-writing
    vs research vs idle-scan vs orchestrator), stagger rule, memory seeding.

## 14. Memory Files
    Source: vidux-claude L336-362
    Content: append-only log, entry format, reset markers, last-10 visibility.

## 15. Lean Fleet Dispatch Rules
    Source: vidux-claude L565-577
    Content: 7 prioritized rules (hard cap, max 3-4 parallel, fire-and-forget,
    trust memory.md, don't bloat parent, absorb duplicate fires, batch waves,
    prefer coordinator).

## 16. Deferred Tool Loading
    Source: vidux-claude L16-26
    Content: ToolSearch for CronCreate/CronDelete/CronList, TaskCreate, WebFetch.

## 17. External Tool Pairing
    Source: vidux-codex L343-374
    Content: nia pairing (package source 16.5x win), nia deep-mode warning (T14),
    amp pairing (prompt amplification for vague tasks).

## 18. Recommended Agent Config Rules
    Source: guides/agent-config-rules.md (cross-reference)
    Content: 3 rules (re-read before edit, re-read after fail, proportional
    response) + T1-T4 change classification framework.

## 19. Activation
    New section combining activation triggers from all three sources.

## 20. Related Skills
    Trimmed table: vidux (core), captain, pilot, amp, nia, ledger.
```

---

## Personal References Found (72 identified)

| File | Line | Reference | Action |
|---|---|---|---|
| vidux-claude | L13 | "Leo's fleet is migrating Codex automations" | Genericize to "fleets migrating from Codex" |
| vidux-claude | L67 | "Leo rotates through 4 accounts for quota management" | Genericize to "multi-account rotation for quota management" |
| vidux-claude | L152 | "When Leo opens ONE memory.md to diagnose" | Genericize to "the operator opens ONE memory.md" |
| vidux-claude | L154 | "When Leo switches accounts" | Genericize to "on account switch" |
| vidux-claude | L175 | "When something goes sideways, Leo needs to scan" | Genericize to "the operator needs to scan" |
| vidux-claude | L176 | "When Leo switches accounts, every running cron dies" | Genericize to "on account rotation, running crons die" |
| vidux-claude | L178 | "Leo has 4" | Genericize to "multiple accounts" |
| vidux-claude | L187 | "Leo's active fleet (2026-04)" | Genericize to "Example fleet layout" |
| vidux-claude | L189 | `leojkwan-coordinator` lane name | Genericize to `<project-a>-coordinator` |
| vidux-claude | L190 | `strongyes-coordinator` lane name | Genericize to `<project-b>-coordinator` |
| vidux-claude | L191 | `session-gc` (ok — generic) | Keep |
| vidux-claude | L192 | `qa-iterator` (ok — generic role name) | Keep |
| vidux-claude | L196 | "leojkwan + strongyes" observers | Genericize to `<project-a>` + `<project-b>` |
| vidux-claude | L196 | "resplit-web" third coordinator | Genericize to `<project-c>` |
| vidux-claude | L216 | "leojkwan" in measurement example | Genericize to "the same project" |
| vidux-claude | L227 | "A/B against Codex" paragraph | Drop (Codex deprecated) |
| vidux-claude | L280 | "Do NOT create named specialist lanes like `leojkwan-shipper` / `strongyes-product` / `resplit-ios-shipper`" | Genericize: "Do NOT create named specialist lanes like `<project>-shipper` / `<project>-product`" |
| vidux-claude | L427 | `~/Development/strongyes-web/` example path | Genericize to `~/Development/<project>/` |
| vidux-claude | L427 | `strongyes-web-worktrees` | Genericize to `<project>-worktrees` |
| vidux-claude | L435 | "Never push without explicit Leo authorization" | Genericize to "explicit human authorization" |
| vidux-claude | L440 | "On Leo's setup" | Genericize to "on some setups" |
| vidux-claude | L534 | "Leo reads the signal in the terminal" | Genericize to "the human reads the signal" |
| vidux-claude | L565 | "(Leo direct 2026-04-15)" | Strip attribution |
| vidux-claude | L570 | "on the same repo causes git worktree contention" | Keep (no personal ref — fine) |
| vidux-codex | L83 | "verified overnight 2026-04-13" | Keep date reference (evidence, not personal) |
| vidux-codex | L106 | "Frankenstein experiment (2026-04-10/11)" | Keep experiment name (evidence trail) |
| vidux-codex | L130 | "Leo's actual constraint" | Genericize to "the common constraint" |
| vidux-codex | L131 | "Leo's actual constraint: Claude Code credits metered, Codex fast subscription unlimited" | Genericize to "common constraint: Claude metered, Codex unlimited" |
| vidux-codex | L304 | "verified 2026-04-13 on iOS live-share fix" | Keep date but genericize: "verified on an iOS live-share fix" |
| vidux-codex | L308-309 | "Resplit/Features/LiveShare/LiveShareActor.swift" paths | Genericize to `<project>/Features/LiveShare/LiveShareActor.swift` |
| vidux-codex | L325 | "T73's scope" | Keep (experiment reference) |
| vidux-codex | L408 | "Leo's fleet" | Genericize to "the fleet" |
| vidux-codex | L560 | "leojkwan fleet (2026-04-15)" | Genericize to "the fleet" |
| vidux-codex | L626 | "~/Development/vidux-codex-experiment/" path | Genericize to "the experiment directory" |
| vidux-fleet | L9 | "Leo's fleet" (implicit — not explicit) | No action needed |
| vidux-fleet | L355 | "Beacon/Acme 2.0-style '1hr/week Wednesday' cycles" | Keep — uses generic project names |
| vidux-fleet | L369 | "Leo is heads-down for hours" | Genericize to "the operator is heads-down" |
| vidux-fleet | L436 | "Leo says 'deep work'" in decision tree | Genericize to "operator says 'deep work'" |
| vidux-fleet | L456 | "Distinct surfaces: 4 (Live Split, receipt-detail, screenshots, AP539)" | Genericize surface names to `(Surface A, Surface B, Surface C, Ticket-539)` |
| vidux-fleet | L458 | "Repos: 1 (acme-ios)" | Keep `acme-ios` — it's already a generic example name |

### Summary of personal reference categories

| Category | Count | Action |
|---|---|---|
| "Leo" name references | 22 | Genericize to "the operator/human" |
| Specific project names (leojkwan, strongyes, resplit, snowcubes) | 18 | Genericize to `<project-a>`, `<project-b>`, `<project-c>` |
| Account rotation details (4 accounts, specific rotation) | 5 | Genericize to "multi-account rotation" |
| Specific file paths (~/Development/strongyes-web/, Resplit/ paths) | 8 | Genericize to `<project>/` |
| Lane names (leojkwan-coordinator, strongyes-coordinator, etc.) | 9 | Genericize to `<project>-coordinator` etc. |
| Attributions ("Leo direct", dated Leo quotes) | 6 | Strip |
| Experiment paths (~/Development/vidux-codex-experiment/) | 2 | Genericize |
| Generic project refs (acme, beacon — already fine) | 2 | Keep |
| **Total** | **72** | |

---

## DEAD Content Summary (lines to drop)

| File | Lines | Reason |
|---|---|---|
| vidux-claude | L63-74 | Routines comparison — superseded by Decision Log 2026-04-15 |
| vidux-claude | L77-87 | vidux-claude specific subcommands — replaced by vidux-auto |
| vidux-claude | L391-404 | Legacy Codex fleet scan — Codex deprecated |
| vidux-claude | L406-418 | A/B testing with /codex — Codex deprecated |
| vidux-claude | L591-619 | Activation + Related Skills — replaced by vidux-auto |
| vidux-codex | L1-4 | Frontmatter — replaced |
| vidux-codex | L12-37 | Scheduling primitive — overlap with vidux-claude (keep claude version) |
| vidux-codex | L441-455 | Activation — replaced |
| vidux-codex | L600-608 | skills-as-commands meta — Claude Code version-specific |
| vidux-codex | L610-622 | Related Skills — replaced |
| vidux-fleet | L1-4 | Frontmatter — replaced |
| vidux-fleet | L6-10 | Intro with Routines priority — DEAD per Decision Log |
| vidux-fleet | L37-38 | "Claude Routines: `/schedule list`" discovery — DEAD |
| vidux-fleet | L111-121 | Claude Routine config generation — DEAD |
| vidux-fleet | L131-155 | Codex automation.toml template — DEAD (legacy) |
| vidux-fleet | L248-253 | vidux-recipes frontmatter — merged |
| vidux-fleet | L489-491 | `--target routine` flag — DEAD |
| vidux-fleet | L603-609 | Routine execution path — DEAD |

**Total DEAD lines: ~280** (of 1,998 total across three files = 14% reduction from drops alone)

---

## OVERLAP Resolution Table

| Topic | vidux-claude | vidux-codex | vidux-fleet | Resolution |
|---|---|---|---|---|
| 24/7 Fleet Model | L28-75 (full) | L12-37 (summary) | -- | Keep claude (full), drop codex (summary) |
| Coordinator pattern | L143-156 | -- | L91-107 (template) | Keep claude (rationale) + fleet (template) |
| Observer pairs | L158-167 (heuristic) | L396-430 (full setup) | L224-250 (recipe) | Keep codex (full) as primary, claude heuristic merged in |
| Delegation modes | L249-280 (summary) | L39-97 (full) | -- | Keep codex (full), drop claude summary |
| Prompt structure | L230-247 (8-block spec) | -- | L50-107 (templates) | Keep both — spec + templates |
| Recipe catalog | -- | L558-598 (qa-iterator) | L278-389 (6 recipes) | Merge: fleet recipes as quick-ref, codex qa-iterator as Recipe 6 |
| Memory.md format | L336-362 (full) | L432-439 (checkpoint only) | -- | Keep claude (full), merge codex checkpoint format in |
| CronCreate cadence | L301-311 (table) | -- | L47-49 (defaults) | Keep claude (detailed table), fleet defaults redundant |
| Worktree discipline | L420-442 (full) | -- | -- | Single source — migrate from claude |
| Session GC | L486-563 (full) | L31 (mention) | -- | Single source — migrate from claude |
| Lean dispatch | L565-577 (full) | -- | -- | Single source — migrate from claude |

---

## Estimated vidux-auto Size

| Source | Lines migrated | After dedup | After personal scrub |
|---|---|---|---|
| vidux-claude (619) | ~430 (minus DEAD+CORE) | ~380 (minus overlaps) | ~350 |
| vidux-codex (626) | ~440 (minus DEAD+CORE) | ~370 (minus overlaps) | ~350 |
| vidux-fleet (753) | ~520 (minus DEAD) | ~420 (minus overlaps) | ~400 |
| NEW (PR Nurse, intro, activation) | +80 | +80 | +80 |
| **Total** | ~1,470 | ~1,250 | **~1,180** |

**Note:** The 1,180 estimate exceeds the ~800-1000 target in PLAN.md. Further compression
will happen during actual section writing (8.2-8.5) by:
- Trimming verbose examples (fleet recipes -> quick-ref table pointing to guides/recipes.md)
- Condensing cadence tables and measured data into tighter formats
- Cutting experiment backstory paragraphs to 1-2 sentence references

Target remains achievable at 900-1000 lines with aggressive editing.
