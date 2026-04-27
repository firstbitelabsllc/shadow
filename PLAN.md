# Vidux v3 — Simplification Revamp

## Purpose
Strip vidux down to its essence: plan first, code second. Remove Redux jargon, circuit breakers, auto-pause, and all fleet ops machinery that belongs in /codex. Rewrite all 12 Codex automations to use the simplified v3 gate pattern. Each automation retains its job — just with a cleaner, shorter prompt.

## Evidence
- [Source: staff review agents, 2026-04-09] 15 doctrines → 6. 1100 lines → 200. Redux analogy costs more than it teaches.
- [Source: plan clobber postmortem, 2026-04-09] Gate was too blunt (dirty=stop). Needs green/yellow/red triage.
- [Source: release-train parking, 2026-04-09] Automation saw file casing collision and said "hold" when it could have fixed it.
- [Source: overnight fleet data, 2026-04-08-09] vidux-loop.sh circuit breakers caused auto-pause on automations doing real branch-push work.
- [Source: nia_research, 2026-04-12] Anthropic Claude Code best practices: "Start minimal, add skills after 2 weeks of production use proves the need." OpenAI Codex best practices: "Test skills with evals to find overlap."
- [Source: ai/skills/ inventory, 2026-04-12] 54 skills, 12,830 total lines. 8 skills are bulk-import cruft with zero project references. 5 skill pairs overlap.
- [Source: design skill audit, 2026-04-12] Naming convention shipped: brand-* (identity), craft-* (platform), figma-* (workflow). 4 renames + 1 new (brand-leojkwan). All cross-refs updated (11 lane prompts, 4 skill files). Zero stale references.

## Constraints
- ALWAYS: Contract tests (test_vidux_contracts.py) must pass before any SKILL.md or PLAN.md change ships
- ALWAYS: Every automation prompt must include TRUNK HEALTH gate (Doctrine 15)
- NEVER: Use re.sub or sed to patch TOML prompt fields — always regenerate from DB (Bug #22)
- NEVER: Accept --theirs or --ours blindly in merge conflicts — preserve both sides (Doctrine 16)

## Tasks

### Phase 1: SKILL.md v3 — core rewrite


### Phase 2: Resplit automation revamp [spawns: investigations/resplit-revamp.md]


### Phase 3: StrongYes automation revamp [spawns: investigations/strongyes-revamp.md]


### Phase 4: Fleet infrastructure


### Phase 5: Ready-PR architecture [in_progress]

**Goal:** All automation pushes go through PRs, never direct-to-main. Operational PRs open ready-for-review by default so review bots, preview comments, and CI gates run immediately; draft is reserved for true WIP or a missing gate. PRs are the **durable source-of-truth for in-flight work** — if a local worktree dies, `gh pr list` is the recovery manifest. Each PR carries: automation id, plan task id, last pushed diff, and the resume point. Closes the Phase 2.4 loop (130 stranded resplit-ios branches with no PR metadata). Formalizes the 2026-04-09 remote-trigger direction. Eliminates the COPY SAFETY-class incident (5ef4498c) without blocking review automation behind draft status.

**Scope (Leo 2026-04-11):** This is a huge change up — every automation today works local-worktree → branch-push → merge-back-to-main. Phase 5 rolls out incrementally in waves.

**Side effects are agnostic (Leo 2026-04-11, refined 2026-04-26):** This plan covers ONLY the cloud-agnostic PR mechanics. Paid-service integrations and review-bot specifics live in `/vidux` Part 2 / repo overlays as composable add-ons after the core works. Core ships independently. Research: `investigations/paid-tooling-pr-integration.md`.

**Rollout (wave-based, reversible at every step):**
1. **Wave 0 — Plan + audit.** Lock the plan, audit current push behavior, Leo answers open Qs. No production changes.
2. **Wave 1 — Reference implementation.** Historical draft-first pilot proved branch + PR safety. Current doctrine is ready-PR-first; document lessons in `guides/draft-pr-flow.md`.
3. **Wave 2 — Batch.** Apply the reference to 3-4 more lanes. Mix shipping + idle.
4. **Wave 3 — Full fleet.** All push-capable automations on ready-PR flow.
5. **Wave 4 — Lock the gate.** Branch protection rejects direct-main pushes from automation actors. Never before Wave 3 completes.

Every wave boundary is reversible. Leo gates each transition.

#### Wave 0 — Plan + audit [completed]

#### Wave 1 — Reference implementation [completed]
- [completed] 5.1.1 Modified `~/.claude/automations/strongyes-coach-p0/prompt.md`: ACT section changed from "merge to main" to "push branch + draft PR". PUSH POLICY replaced: 5-step flow (push branch → `gh pr create --draft` → never direct-to-main → sync main each cycle → fallback on `gh` failure). PR body template carries lane id, plan task, resume point. [Done: 2026-04-11]
- [completed] 5.1.2 Draft-PR mechanics validated end-to-end on vidux repo (leojkwan/vidux#4). Branch push → `gh pr create --draft` → `gh pr list` (visible, isDraft: true) → close + cleanup. coach-p0 plan was CLOSED (no work to ship), so tested directly instead. Friction: zero — `gh` CLI worked cleanly. Surprise: coach-p0 can't be the production pilot (plan closed); need a lane with active work for Wave 2. [Done: 2026-04-12]
- [completed] 5.1.3 Wrote `guides/draft-pr-flow.md` — cloud-agnostic core doctrine: the 5-step flow, branch naming convention, PR body template, recovery via `gh pr list`, fallback on `gh` failure, adoption snippet for lane prompts. [Done: 2026-04-12]

#### Wave 2 — Batch rollout (3 lanes) [completed]
- [completed] 5.2.1 Picked 3 lanes with active plans: `strongyes-backend-trust` (26p+25ip, high-vol), `strongyes-blog-pipeline` (8p, content), `resplit-revamp-executor` (12p+1ip, iOS shipping). [Done: 2026-04-12]
- [completed] 5.2.2 Applied draft-PR pattern from `guides/draft-pr-flow.md` to all 3 lane prompts: ACT sections updated (no merge to main, push branch + draft PR), PUSH POLICY replaced with 5-step flow, fallback on `gh` failure. [Done: 2026-04-12]
- [completed] 5.2.3 Observer-pair audit. strongyes lanes PASS (PR #283 open DRAFT, 10+ merged today by Leo). resplit-ios BLOCKED: `gh pr create` fails 4x with "shared commit overlaps with an existing PR" — lanes are following the draft-PR prompt but `gh` rejects when new branches share ancestry with old branches/PRs. [Done: 2026-04-14]
- [completed] 5.2.4 Doctrine correction: ready-PR-first supersedes draft-first for operational PRs because review automation skips or delays drafts. Updated core docs/templates while preserving `guides/draft-pr-flow.md` path for link stability. [Done: 2026-04-26]

#### Wave 3 — Full fleet
- [completed] 5.3.0 Worktree lifecycle finalizer: classify local worktrees by PR state, merge status, and dirty state; provide a safe explicit cleanup path for PR-first lanes so Wave 3 does not recreate the 130+ stranded-worktree failure. [Evidence: 2026-04-26 StrongYes worktree audit found 157 worktrees; `guides/fleet-ops.md` still described direct merge-back despite ready-PR doctrine] [Done: 2026-04-26; shipped `scripts/vidux-worktree-gc.py`, docs, and tests]
- [pending] 5.3.1 Remaining ~10 automations. [Depends: Wave 2 complete ✓ — but resplit `gh pr create` overlap issue must be solved first for resplit lanes]
- [pending] 5.3.2 Validate `gh pr list` shows in-flight PR per active lane. [Depends: 5.3.1]

#### Wave 4 — Lock the gate
- [pending] 5.4.1 Branch protection: reject direct-main pushes from automation actors, preserve human pushes. [Depends: Wave 3 complete]
- [pending] 5.4.2 Smoke test both paths. [Depends: 5.4.1]

### Phase 6: Skill consolidation — 54 → ~42 skills [completed]

**Goal:** Cut dead weight and merge overlapping skills. 54 skills is bloat — vendor research (Anthropic + OpenAI) says: "earn your complexity" and "eval-driven pruning." Description quality drives activation (20%→90% with optimized descriptions per Anthropic testing). Every unused skill is noise in the routing table.

**Approach:** Three tiers. Tier 1 (delete) and Tier 2 (merge) are safe — evidence is clear. Tier 3 needs Leo's call.

#### Tier 1 — DELETE dead weight (8 skills, ~1,294 lines)

Bulk-import cruft from Codex skill installer. Zero project references in any lane prompt or PLAN.md.

- [completed] 6.1.1 Delete `hooks` — done 2026-04-12
- [completed] 6.1.2 Delete `jed` — done 2026-04-12
- [completed] 6.1.3 Delete `atlas` — done 2026-04-12
- [completed] 6.1.4 Delete `greenapple` — done 2026-04-12
- [completed] 6.1.5 Delete `judge0` — done 2026-04-12
- [completed] 6.1.6 Delete `doc` — done 2026-04-12
- [completed] 6.1.7 Delete `jupyter-notebook` — done 2026-04-12
- [completed] 6.1.8 Delete `spreadsheet` — done 2026-04-12

#### Tier 2 — MERGE overlapping skills (5 merges, net -5 skills)

- [completed] 6.2.1 Merge `ahrefs-seo` into `seo` — done 2026-04-12 (3 lane prompt refs updated)
- [completed] 6.2.2 Fold `figma` into `figma-implement` — done 2026-04-12 (MCP rules + references merged)
- [completed] 6.2.3 Merge `vidux-loop` + `vidux-recipes` → `vidux-fleet` — done 2026-04-12 (symlinks swapped)
- [completed] 6.2.4 Fold `vidux-version` + `vidux-status` — removed as standalone commands, done 2026-04-12
- [completed] 6.2.5 Delete `splitter` — done 2026-04-12 (Leo: "can be deleted")

#### Tier 3 — EVALUATE with Leo (needs human judgment)

- [completed] 6.3.1 `codex` (455 lines) — Deleted. Codex fleet deprecated, vidux is the super champ now. [Done: 2026-04-12]
- [completed] 6.3.2 `multithready` (198 lines) — Deleted. Worktree isolation absorbed by bigapple. [Done: 2026-04-12]
- [completed] 6.3.3 Fold `resplit-engineering` into `bigapple` — done 2026-04-12 (9 lane prompt refs updated). Leo confirmed.
- [completed] 6.3.4 `imagegen` — KEEP. Leo: "yes i think i do"
- [completed] 6.3.5 `maily` — KEEP. Leo: "yes i use maily"
- [completed] 6.3.6 Merge `media-studio` + `fcp` → `media` — done 2026-04-12 (2 lane prompt refs updated). Leo confirmed.

### Phase 7: First-Class Automation Recipes + Claude Routines [completed]

**Goal:** Upgrade vidux's automation layer from CronCreate/Codex automations to Claude Routines. Codify opinionated, ready-to-deploy recipes for common patterns. Make automation a first-class part of vidux, not an afterthought. Include Greptile-powered PR review and code-reviewer pipelines.

**Why now:** Claude Routines shipped 2026-04-14 (research preview). Cloud-native, persistent, three trigger types (scheduled, API, GitHub events). Supersedes session-scoped CronCreate and the old `claude.ai/code/scheduled` triggers. This is the upgrade path.

**Evidence:**
- [Source: claude.com/blog/introducing-routines-in-claude-code] Routines: scheduled (cron), API (POST /fire), GitHub events (webhooks). Pro=5/day, Max=15/day.
- [Source: 2026-04-14 fleet run] CronCreate lanes die when session closes. Routines survive across sessions.
- [Source: Leo 2026-04-14] "i want our system with greptile and code reviewers codified, though opinionated in how we work"
- [Source: PLAN.md Phase 5] PR flow is the safety layer. Recipes build on top of it.
- [Source: guides/fleet-ops.md] Existing fleet patterns (gates, observers, coordinators) need Routines-native rewrites.

#### 7.1 — Recipes guide [in_progress]
- [completed] 7.1.1 Write `guides/recipes.md` — 8 opinionated recipes with full prompt templates, trigger configs, and when-to-use guidance. Recipes: Fleet Watcher, PR Reviewer (Greptile + code-reviewer), Draft-PR Lifecycle, Observer Pair, Deploy Watcher, Trunk Health, Skill Refiner, Self-Improvement Loop. [Done: 2026-04-15 — 517 lines, all 8 recipes present (verified grep -c "^## Recipe"), Routines primer integrated at L11-70]
- [completed] 7.1.2 Write `guides/routines.md` — Closed as redundant. All four scope items (three trigger types, migration from CronCreate, daily limits, cadence planning) are already in guides/recipes.md: "How Routines Work" L11-70 (triggers + key details), "Hybrid Strategy: Routines + CronCreate" L491-502 (migration), "Daily Budget Planning" L474-489 (limits + cadence). A separate routines.md would duplicate 90%+ of recipes.md and invite drift. See Decision Log 2026-04-15.
- [completed] 7.1.3 Update `commands/vidux-fleet.md` — Routines as primary primitive, Codex automation.toml marked legacy. [Done: 2026-04-15 — surgical edit: top description, discover/inventory/audit scan paths, `create` config section (Claude Routine primary → CronCreate lane → Codex legacy), `write` subcommand adds `--target routine|claude-lane|codex-legacy` flag with routine as default. Cross-ref `guides/recipes.md` L11-70 (Routines primer) and L491-502 (Hybrid Strategy). File grew 728→753 lines.]
- [completed] 7.1.4 Update README.md Fleet Intelligence section — mention Routines + link to recipes guide. [Done: 2026-04-15 — added Routines primitive priority (scheduled/GitHub/API) + direct anchor links to recipes.md #how-routines-work and #hybrid-strategy-routines--croncreate. Also cleaned stale `routines` reference in guides/ table (was pointing at the now-closed 7.1.2 file).]
- [completed] 7.1.5 ~~Update SKILL.md — add Routines as first-class automation primitive.~~ **Direction reversed 2026-04-15:** Routines are cloud-based, vidux core stays local-first and platform-agnostic. SKILL.md already mentions CronCreate and companion skills — no Routines addition needed. Instead: strip Routines references from README.md and guide files added during Phase 7. [Done: 2026-04-16. README.md scrubbed during 7.1.4. guides/recipes.md fully scrubbed this cycle — replaced "How Routines Work" platform-specific primer with "Trigger Types (platform-agnostic)", genericized Recipe 2 (stripped Greptile/mcp__greptile specifics, "Leo promotes"→"human promotes", READY_FOR_LEO→READY_FOR_HUMAN), replaced "Leo's Fleet" diagram with "Production Fleet", replaced "Daily Budget Planning"+"Hybrid Strategy: Routines + CronCreate" with "Cadence Planning"+"Hybrid Strategy: Persistent + Session-scoped", genericized Anti-Patterns (Routines→lanes), Codex Delegation→Secondary-Model Delegation. Verification grep on Routines|Greptile|Leo|Sentry|Seer|Nia|claude.ai returns 0 hits. Contract tests: 141/144 pass (3 pre-existing failures).]

### Phase 8: Consolidate companion skills into `/vidux-auto` + PR Nurse pattern [blocked]
**Superseded by Phase 10** (single entry point /vidux, Part 1 + Part 2, shipped commit 8c1f593 2026-04-17). Kept as historical record; do not execute.


**Goal:** Merge `/vidux-claude` (619 lines) + `/vidux-codex` (626 lines) + `/vidux-fleet` (753 lines) into a single `/vidux-auto` companion skill (~800-1000 lines after dedup + scrub). Strip all personal references (Leo's fleet, strongyes/resplit lane names, account rotation details). Add the PR Nurse pattern to close the feedback gap. Ship as two clean OSS artifacts: `vidux` (core discipline) + `vidux-auto` (automation layer).

**Why now:** Three companion skills with 1,998 combined lines have significant overlap (CronCreate referenced 35x across all three, observer pairs 32x, memory.md 44x, checkpoints 39x). Personal references total ~62 across the three files. Nobody installs `/vidux-claude` without wanting `/vidux-fleet`. The PR feedback gap (PR #338: P1 unaddressed, merged anyway) proves the current split loses critical patterns between skills.

**Evidence:**
- [Source: grep audit 2026-04-15] vidux-claude has ~50 personal refs (Leo's fleet, account rotation, specific lane names like `leojkwan-coordinator`, `strongyes-coordinator`). vidux-codex has ~4 (mostly generic). vidux-fleet has ~8 (`Leo` name refs).
- [Source: overlap detection 2026-04-15] CronCreate: claude=16, codex=9, fleet=10 mentions. Observer: claude=9, codex=23. Memory.md: claude=28, codex=9, fleet=7. Checkpoint: claude=14, codex=10, fleet=15. Heavy cross-referencing = content wants to be together.
- [Source: PR #338 strongyes-web] Greptile posted 1 P1 (glossary terms missing, 5 popovers silently degrade) + 2 P2s (pattern prop casing). Zero fix commits. Merged by Leo. The PR triage rule EXISTS in vidux-claude L445 ("mandatory first action of every cron cycle") but the blog-builder lane doesn't include it. The qa-iterator recipe EXISTS in vidux-codex L560 but was killed as a ScheduleWakeup bloat amplifier.
- [Source: contract tests 2026-04-15] 142/144 pass. 2 pre-existing failures in ledger bimodal (not related). Core planning/cycle/investigation tests: 23/23 pass.
- [Source: session bloat diagnosis 2026-04-15] The three companion skills contribute ~7% of session JSONL size (skill listings loaded per-turn). Fewer skills = less per-turn overhead.

**Constraints:**
  - ALWAYS: vidux core SKILL.md stays platform-agnostic (no CronCreate specifics, no Claude Code assumptions)
  - ALWAYS: vidux-auto is a single file that works as a Claude Code skill AND as a reference doc for Cursor/Codex users
  - ALWAYS: strip ALL personal references (Leo, strongyes, resplit, leojkwan, snowcubes, Snap, Nicole, Pickles, account rotation, specific lane names). Use `<project>`, `<coordinator>`, `<writer>` generics.
  - NEVER: lose operational patterns during the merge. Every non-personal pattern from the three sources must survive in vidux-auto.
  - NEVER: duplicate content that's already in vidux core SKILL.md (observer pair description, delegation concept, investigation template)

#### 8.0 — Content audit + migration map [completed]

1. Read all three source files line by line. For each section, classify:
   - **CORE** = already in vidux SKILL.md (skip)
   - **AUTO** = goes into vidux-auto (migrate)
   - **PERSONAL** = Leo-specific (strip or genericize)
   - **DEAD** = obsolete or contradicted by later Decision Log entries (drop)
   - **OVERLAP** = covered by 2+ sources (merge, keep the best version)
2. Output: a migration map in `evidence/2026-04-16-auto-migration-map.md` with line ranges and classifications.
3. Identify the section structure for vidux-auto (proposed TOC).
[Done: 2026-04-16. Migration map at evidence/2026-04-16-auto-migration-map.md. 72 personal refs identified (vs 62 estimated). ~280 DEAD lines (14%). 11 overlap resolutions documented. 20-section TOC proposed. Estimated vidux-auto: ~1,180 lines pre-compression, target 900-1000 after aggressive editing in 8.2-8.5.]

#### 8.1 — Create `/vidux-auto` skeleton [completed] [Depends: 8.0]

1. Created `commands/vidux-auto.md` with frontmatter and 20-section TOC from migration map.
2. Each section has: header, 1-2 sentence description, `<!-- SOURCE: ... -->` comment pointing to source material.
3. Cross-references to `guides/agent-config-rules.md`, `guides/recipes.md`, `guides/draft-pr-flow.md`, `guides/fleet-ops.md` instead of inlining.
4. Zero personal references. Uses `<project>`, `<coordinator>`, `<writer>`, `<observer>` generics.
5. Skeleton is ~190 lines — headers + source pointers + brief descriptions only. Migration tasks 8.2-8.5 will fill the body sections.
[Done: 2026-04-16]

#### 8.2 — Migrate + scrub: session management [completed] [Depends: 8.1]

Migrate from vidux-claude L54-76 (hot/cold storage), L486-565 (session GC), L565-578 (lean dispatch).
Strip: Leo's fleet sizes, specific session IDs, account rotation details.
Genericize: `<your-project>`, `<coordinator>`, estimated sizes as ranges not absolutes.
[Done: 2026-04-16. Migrated + scrubbed 6 sections: Section 1 (24/7 Fleet Model — lane/session diagram, hot/cold table, cloud scheduling rejection), Section 2 (Session Management — JSONL growth anatomy, 3 GC levels, session-gc lane spec, cycle signal, plan-GC rule), Section 7 (Concurrent-Cycle Hazards — 3 verified hazards + prevention checklist), Section 9 (Worktree Discipline — isolation rules, lint-staged gotcha), Section 14 (Lean Fleet Dispatch — 7 prioritized rules), Section 15 (Deferred Tool Loading — ToolSearch prerequisite). File grew 252 → 387 lines. grep -i personal-refs returns 0 hits.]

#### 8.3 — Migrate + scrub: lane management [completed] [Depends: 8.1]

Migrate from vidux-claude L117-220 (decision tree, coordinator pattern, 6-lane cap, anti-patterns, polish-brake).
Strip: Leo's active fleet example (L187-196), qa-iterator lane name, strongyes/resplit references.
Genericize: example fleet as `<project-a>` / `<project-b>` with role labels.
[Done: 2026-04-16. Migrated + scrubbed 4 sections: Section 3 (Lane Management — decision tree, coordinator pattern with 5 rationale bullets, observer intro + when-to-add heuristic, 6-lane hard cap with measured evidence, 5 anti-patterns, ghost lane detection, polish-brake trigger), Section 10 (Prompt File Structure — disk-persisted authority rationale, 8-block structure spec, <=15 line harness rule, cross-ref to fleet-ops templates), Section 12 (Creating/Updating/Deleting Lanes — 5-step create workflow, cadence table with 4 lane types + 15-min retirement, stagger rule, update/delete workflows), Section 13 (Memory Files — entry format, dual-token delegation checkpoint format from vidux-codex L432-439, reset markers, last-10 visibility rule). File grew 387 -> 550 lines. grep -i personal-refs returns 0 hits.]

#### 8.4 — Migrate + scrub: delegation modes [completed] [Depends: 8.1]

Migrate from vidux-codex L39-97 (Mode A/B), L136-187 (decision tree), L207-330 (invocation flags, compression contract, implementation prompt).
Strip: Framing B personal cost context (L130 "Leo's actual constraint"), experiment paths.
Keep: the tier table (L182-184), the decision tree, the diff-review checklist (L331-341).
[Done: 2026-04-16. Migrated + scrubbed 5 vidux-codex sections into vidux-auto: Section 4 (Delegation — Mode A/B flow diagrams, cost shift table, decision tree, tier math, compression contract, implementation prompt shape, diff-review checklist, invocation mechanics, 9 execution rules), Section 8 (Observer Pairs — what observers catch, setup recipe, authority discipline, verdict format, when-to-add heuristic), Section 11 (Composition Recipes — 6 recipes expanded: vidux->delegated, prompt amplifier, research agent, parallelism, Agent wrapper for long crons, qa-iterator), Section 16 (External Tool Pairing — research agent pairing with deep-mode warning, prompt amplifier pairing). All "Claude/Codex" refs genericized to "primary/secondary model". grep -i personal-refs returns 0 hits. grep -i codex returns 1 hit (intro mentioning former skill names). File at 811 lines.]

#### 8.5 — Migrate + scrub: fleet operations [completed] [Depends: 8.1]

Migrate from vidux-fleet L22-145 (create), L149-177 (fleet/list), L180-200 (validate), L380-461 (prescribe), L465-621 (write), L625-715 (audit).
Strip: Leo sprint reference (L369, L436), `acme-` examples are already generic (keep).
Simplify: the 6 recipes can be trimmed to reference `guides/recipes.md` instead of inlining full prescriptions.
[Done: 2026-04-16. Migrated fleet ops into vidux-auto Section 5 (~97 lines across 6 subsections: Discover+Slot Map, Prompt Templates summary table, Bimodal Quality Model, Validation Rubric 9-check table, Prescription heuristics table, Hard Rules). All personal refs scrubbed. Recipes summarized as quick-ref tables pointing to guides/recipes.md. grep -i personal-refs returns 0 hits.]

#### 8.6 — Add PR Nurse pattern (Recipe 9) [completed] [Depends: 8.1]

New content — closes the feedback gap proven by PR #338.
1. Add Recipe 9 to `guides/recipes.md`: PR Nurse.
2. Add a "PR lifecycle" section to vidux-auto that makes PR triage mandatory at cycle start (absorbing vidux-claude L445 "Open PR triage" into the unified skill).
3. PR Nurse responsibilities:
   - READ: `gh pr list --state open --author @me` → filter to automation-created PRs
   - For each: `gh api repos/.../pulls/N/comments` → find unaddressed P1/P2
   - ACT: fix ONE issue per cycle, push to the PR branch, reply to comment thread
   - VERIFY: CI green (remote) or local build pass (repos without CI)
   - For repos without remote CI: run local checks (build, lint, type-check), post results as PR comment
   - SIGNAL: when all comments resolved + CI green → post "READY_FOR_MERGE" comment
4. Bake PR triage into the writer prompt template (not a separate lane — the writer nurses its own PRs).
5. Update `guides/draft-pr-flow.md` with a "Step 0: Self-review before push" checklist.
[Done: 2026-04-16. PR Lifecycle section filled in vidux-auto Section 6 (~38 lines across 3 subsections: Triage at cycle start, PR Nurse responsibilities with 5-step flow, Self-review before push checklist). References guides/draft-pr-flow.md and guides/recipes.md Recipe 9. Note: Recipe 9 addition to guides/recipes.md itself is a separate deliverable — Section 6 references it but the recipe template in the guide needs its own PR.]

#### 8.7 — Update vidux core references [completed] [Depends: 8.2, 8.3, 8.4, 8.5, 8.6]

1. Update SKILL.md "Automation is platform-specific" section: replace `/vidux-claude` + `/vidux-codex` references with `/vidux-auto`.
2. Update README.md ecosystem table: one `/vidux-auto` row instead of three.
3. Update README.md Fleet Intelligence section: point to vidux-auto for mechanics.
4. Update any `guides/` cross-references that point to old skill names.
[Done: 2026-04-16. SKILL.md updated (companion skills section → single /vidux-auto reference). README.md updated (ecosystem table: 3 rows → 1 /vidux-auto row; commands table: vidux-fleet/vidux-claude → vidux-auto; Platform Automation section rewritten to reference vidux-auto; Fleet Patterns section updated). 3 guides/ cross-refs fixed: harness.md (vidux-fleet → /vidux-auto), draft-pr-flow.md (/vidux-codex → /vidux-auto), recipes.md (/vidux-codex Mode A → /vidux-auto Mode A).]

#### 8.8 — Deprecation markers [completed] [Depends: 8.7]

1. Add `deprecated: true` frontmatter + pointer to vidux-auto at the top of:
   - `~/Development/ai/skills/vidux-claude/SKILL.md`
   - `~/Development/ai/skills/vidux-codex/SKILL.md`
   - `~/Development/vidux/commands/vidux-fleet.md`
2. Do NOT delete the old files — they stay as migration breadcrumbs for 90 days (GC per PLAN.md rules).
3. Update skill symlinks to point to vidux-auto.
[Done: 2026-04-16. Deprecation notice added to all 3 files (blockquote format with date, pointer to commands/vidux-auto.md, 90-day retention note). Files not deleted per plan rules.]

#### 8.9 — Verify + gate [completed] [Depends: 8.7, 8.8]

1. Run `python3 -m pytest tests/` — all 142 non-flaky tests must pass.
2. Verify every cross-reference in vidux-auto resolves (file paths, line numbers, guide anchors).
3. Verify no personal references survive: `grep -i "leo\|strongyes\|resplit\|leojkwan\|snowcube\|snap\b\|nicole\|pickles" commands/vidux-auto.md` returns 0 hits.
4. Verify vidux-auto is ≤ 1,000 lines (the merge should SHRINK from 1,998 by removing overlap and personal content).
5. Spot-check: pick 3 operational patterns from the old skills, verify they exist in vidux-auto.
[Done: 2026-04-16. Gate results: (1) 141/144 tests pass — 3 failures are all pre-existing (2 ledger bimodal, 1 PLAN.md constraint-line regex). (2) Cross-refs verified: agent-config-rules.md OK, recipes.md OK, draft-pr-flow.md OK. (3) Personal refs: 0 hits. (4) Line count: 913 (under 1,000). (5) Spot-check: "observer pair" 2 hits, "delegation" 14 hits, "coordinator" 21 hits — all operational patterns present.]

### Phase 9: Fleet Intelligence & Stability

**Goal:** Protect vidux core from churn while making the fleet smarter. Three deliverables: (1) T1-T4 change classification so insights fix prompts and CLAUDE.md, not core discipline, (2) Codex GC to match Claude's session-prune hygiene, (3) agent config guide for OSS adopters.

**Why now:** /insights report (2026-04-16) confirmed zero T4 (core discipline) changes needed — friction is all implementation-level. Without a framework, every insight mutates core and destabilizes it. Meanwhile Codex is 4 GB with no GC.

**Evidence:**
- [Source: /insights facets 2026-04-16] 10 sessions, 5 friction types. `wrong_approach` 3/10 (dominant). `buggy_code` 2/10. `test_coverage_gap` 1/10. Zero core-discipline failures.
- [Source: codex-gc investigation 2026-04-16] `~/.codex/` = 4.0 GB. `archived_sessions/` 2.7 GB (2,342 files). `logs_2.sqlite` 474 MB (185k rows). Top ROI: DELETE+VACUUM on logs_2.sqlite.
- [Source: codex-config investigation 2026-04-16] 13 automations in TOML, prompt is inline string. Indirection feasible but Codex-to-Claude migration is "effectively complete" (2 Codex observers remain). Most of the 13 are legacy.
- [Source: CLAUDE.md T2 application 2026-04-16] 4 rules applied to `~/.claude/CLAUDE.md`. Already shipped.
- [Source: plan review 2026-04-16] Two review agents scrutinized Phase 9 v1. Verdict: insights aggregator script + 2h cron are overkill (manual triage of 5-10 findings takes 2 min). Dedicated GC lane is overkill (fold into existing fleet-watcher). Codex config migration should be 3 highest-churn only (rest dying). Missing: agent config rules guide for OSS.

**Constraints:**
  - ALWAYS: keep it simple. A CLAUDE.md rule beats a custom hook. Manual triage beats a script until it proves painful.
  - NEVER: build automation to solve a problem that occurs less than weekly.

**Parallelism note:** 9.0, 9.1, 9.2 can run NOW — they do NOT depend on Phase 8 (vidux-auto merge).

#### 9.0 — T1-T4 Change Classification framework [completed]

1. Add a "Change Classification" section to vidux-auto that defines the four tiers:
   - **T1: Prompt** — lane prompt wording. Most insights land here.
   - **T2: Agent config** — global rules in CLAUDE.md / .cursorrules / AGENTS.md. Applied by human.
   - **T3: Companion** — new recipes in guides/recipes.md or vidux-auto. Planned in PLAN.md first.
   - **T4: Core** — vidux SKILL.md principles or contracts. Gate: only when the DISCIPLINE is wrong. Requires Decision Log entry.
2. Rule: work from T1 up. If it can be fixed in a prompt, don't touch CLAUDE.md. If it can be fixed in CLAUDE.md, don't add a recipe.
3. Add to vidux-auto skeleton (Phase 8.1 parallel).

#### 9.1 — Codex static-config convention [completed]

Convention documented in `guides/agent-config-rules.md`. No migration needed — existing 13 Codex automations can be deleted and recreated fresh using the `~/.codex-automations/<name>/prompt.md` pattern when needed. The convention: TOML `prompt` field is a thin shim → external prompt.md file. Edit prompt.md freely without restarting the app. Leo: "we can delete them all and start fresh."

#### 9.2 — Build codex-gc.sh [completed]

1. Bash script at `scripts/codex-gc.sh` with `--dry-run` and `--json` flags. Target: ~50 lines.
2. GC targets (ROI order):
   - `logs_2.sqlite`: DELETE rows older than 7 days, VACUUM (~400 MB)
   - `archived_sessions/`: delete rollout JSONLs older than 14 days, keep newest 50 (~2 GB)
   - `sessions/`: delete dirs older than 30 days, never touch current month
   - `state_5.sqlite`: delete archived threads older than 30 days, VACUUM
3. Safety: skip if Codex processes running, never delete auth/config files.
4. Add `_check_codex_disk_pressure` to vidux-doctor: warn when `~/.codex/` exceeds 2 GB.
5. Run from existing fleet-watcher or session-gc lane — NO dedicated lane.

#### 9.3 — Write guides/agent-config-rules.md [completed]

Platform-agnostic agent hygiene rules for OSS adopters. Named "agent config" not "CLAUDE.md" because vidux works with Claude, Cursor, Codex, and others.

3 battle-tested rules (derived from /insights friction analysis across 10 sessions):
1. **Re-read before editing state files.** Before applying any edit to a plan file, memory file, or state file, re-read the file in the same turn. Stale context causes silent clobbers.
2. **Re-read after failed edits.** After a failed edit (string not found, wrong match), never guess the fix. Re-read the file, then retry with the actual content.
3. **Proportional response.** For simple copy, naming, or creative requests, respond directly with 2-3 options. Don't create plan tasks or investigations for work that takes under 2 minutes.

Cross-reference Principle 5 ("Prove it mechanically") for verification-before-completion — already covered in core, no duplication needed. Reference from vidux-auto's "Recommended Agent Config Rules" section.

#### 9.4 — Insights triage process (manual-first) [completed]

1. Add to vidux-auto: "After every 10 sessions, run `/insights` and review `~/.claude/usage-data/facets/`. Classify each friction finding as T1-T4. Apply T1/T2 immediately. Plan T3. Escalate T4."
2. This is a PROCESS, not a script. Build a script only when manual triage proves painful (>15 findings per review).
3. Profile commands for manual triage:
   ```
   jq -r '[.session_id[:8], .outcome, (.friction_counts | keys | join(","))] | @tsv' ~/.claude/usage-data/facets/*.json
   ```

#### 9.5 — Add T3 recipes to guides/recipes.md [completed]

3 new recipes from /insights (trimmed from 6 — the others are horizon ideas, not battle-tested):
1. `edit-then-verify` — post-edit validation pattern (re-read + diff check)
2. `cron-retry-heal` — retry wrapper for `external_blocker` / `context_overflow` exits
3. `multi-pr-dag` — coordinator pattern for dependency-ordered PR shipping

### Phase 10: Further consolidation — `/vidux-auto` merged into `/vidux` Part 2 [completed]

**Goal:** Collapse the `/vidux` + `/vidux-auto` two-skill split (shipped by Phase 8) into a single `/vidux` entry point with progressive disclosure. Users shouldn't pick between discipline (`/vidux`) and automation (`/vidux-auto`) at invocation time — the skill should route internally.

**Why now:** Leo 2026-04-17: *"to me it just feels like claude and codex vidux merge into vidux auto but i personally don't think users should care, it should just be baked in where if user wants an automation the skill knows how to write the best automation and know how of creating the skill for codex and claude local."* Phase 8 produced a clean `/vidux-auto` artifact, but invocation-time friction proved the split was still architecture-leaking. Single entry + `references/automation.md` progressive disclosure is the final shape.

**Evidence:**
- [Source: Leo 2026-04-17] "users shouldn't have to pick between /vidux (discipline) and /vidux-auto (automation) at invocation time"
- [Source: leojkwan memory 2026-04-17] `feedback_single_entry_skills.md` — preference codified: one /foo skill per concept, not /foo + /foo-auto + /foo-claude siblings
- [Source: commit 8c1f593 2026-04-17] net -2,193 lines across 19 files (5 deleted commands + vidux-auto breadcrumb + SKILL.md Part 2 expansion + references/automation.md NEW + 13 cross-ref updates)

**Constraints:**
  - ALWAYS: preserve every operational pattern from Phase 8's vidux-auto in /vidux Part 2 or references/automation.md (no regression)
  - 2026-04-17 through 2026-04-22: keep Phase 8's artifacts usable while live lane prompts still load `/vidux-auto`
  - 2026-04-22 Leo direct: once active prompts + contract tests stop referencing `/vidux-auto`, delete the deprecated command/skill files and leave only historical mentions in PLAN.md / CHANGELOG.md / evidence

#### 10.1 — Expand SKILL.md to Part 1 + Part 2 [completed]

1. Keep Part 1: Discipline unchanged (five principles, cycle, PLAN.md template, quarter projects, investigations, course correction).
2. Add Part 2: Automation inline — 24/7 fleet model summary, lane management (max 6, coordinator pattern, polish-brake), Mode A/B delegation with compression contract + 5-block spec, lane bootstrap recipe (decision tree + role picker + file templates + registration steps).
3. Cross-ref `references/automation.md` for deep doctrine, loaded on demand not eagerly.
[Done: 2026-04-17 commit 8c1f593. SKILL.md went from 365L (Part 1 only) → 498L (Part 1 + Part 2). Part 2 is 133 lines — lean operational summary, not encyclopedia.]

#### 10.2 — Create references/automation.md [completed] [Depends: 10.1]

1. Absorb Phase 8's `commands/vidux-auto.md` body (913L) into `references/automation.md` (55 KB / ~990L after generics preserved).
2. Update header to note: "This reference contains the full doctrine merged from the former /vidux-claude, /vidux-codex, and /vidux-fleet companion skills." Section 19 activation line changed from "activate /vidux-auto alongside /vidux" to "Read this reference (loaded on demand from within a /vidux session)".
3. Progressive disclosure: SKILL.md Part 2 has the operational summary + decision trees; references/automation.md has session-gc internals, Codex shim registration recipe, PR lifecycle nursing, cross-fleet coordination.
[Done: 2026-04-17 commit 8c1f593. File lives at `references/automation.md`, 19 sections preserved from Phase 8 structure.]

#### 10.3 — Deprecate `/vidux-auto` + prune orphaned commands [completed] [Depends: 10.1]

1. Replace `commands/vidux-auto.md` body with a deprecation breadcrumb: frontmatter flipped to "DEPRECATED (2026-04-17)", body redirects to `/vidux` Part 2 + references/automation.md, 90-day removal target 2026-07-17. [Superseded: 2026-04-22 early delete after active-reference migration.]
2. Delete `commands/vidux-claude.md`, `commands/vidux-codex.md`, `commands/vidux-fleet.md`, `commands/vidux-dashboard.md`, `commands/vidux-manager.md`, `commands/vidux-plan.md` — zero active external references after Phase 8's migration.
3. Sibling ai-skills repo: `~/Development/ai/skills/vidux-auto/SKILL.md` synced to breadcrumb (ai commit 44c09a1).
[Done: 2026-04-17 commit 8c1f593 + ai 44c09a1. 5 command files deleted, vidux-auto replaced with 37-line breadcrumb. Follow-up 2026-04-22: Leo explicitly requested early removal; active prompts/tests migrated, then `commands/vidux-auto.md` + `ai/skills/vidux-auto/SKILL.md` were deleted.]

#### 10.4 — Sync docs + guides cross-refs [completed] [Depends: 10.3]

1. `README.md`: ecosystem table (2 rows → 1 `/vidux`), commands-path row, Platform Automation section rewritten to reference Part 2 + references/automation.md, Fleet Patterns section updated, "Lessons from Production" Mode B line updated.
2. `ARCHITECTURE.md`: file-tree updated (commands single entry, references/ added).
3. `docs/guide/installation.md`: Ecosystem table collapsed (5 rows → 1), deprecation note inline, references/automation.md pointer.
4. `docs/guide/quickstart.md`: "Plan-only" example changed from `/vidux-plan "..."` to `/vidux --plan "..."` + told-instruction variant.
5. `docs/reference/prompt-template.md`: Skills line `/vidux /brand-leojkwan /frontend-design` (no `/vidux-claude`), Delegation example references `/vidux` Part 2.
6. `docs/fleet/platforms.md`: table header dropped deprecated slash-command labels from "Claude Code" / "Codex" column headers.
7. `docs/fleet/codex-lifecycle.md` + `docs/fleet/codex-setup.md`: "See Also" links point to `/vidux` Part 2 + references/automation.md instead of `/vidux-codex` path.
8. `guides/harness.md`, `guides/recipes.md` (4 places), `guides/draft-pr-flow.md`: all `/vidux-auto` / `/vidux-codex` refs updated to `/vidux` Part 2 or references/automation.md.
[Done: 2026-04-17 commit 8c1f593. Net -2,193 lines across 19 files.]

#### 10.5 — Verify cross-ref integrity [completed] [Depends: 10.4]

1. `grep -rn "/vidux-(auto|claude|codex|fleet|dashboard|manager|plan)\b"` on repo: every remaining hit is either intentional (deprecation breadcrumb listing superseded names for search discoverability) or historical (PLAN.md, ARCHIVE.md, evidence/, commands/vidux-auto.md breadcrumb).
2. Pushed to origin/main cleanly (gh `git push origin main`: f552f7d..8c1f593).
3. Sibling ai-skills repo: `~/Development/ai/skills/vidux/` is a symlink into this repo, so OSS update is automatically "installed" on Leo's machine. `skills/vidux-auto/SKILL.md` synced separately (ai commit 44c09a1).
[Done: 2026-04-17. Verified in the same session the merge shipped.]

#### 10.6 — Purge residual `/vidux-auto` mentions [completed] [Depends: 10.5]

Remove any remaining `/vidux-auto` references from non-historical docs, prompts, and tooling.
Historical mentions stay allowed only in `PLAN.md`, `CHANGELOG.md`, `evidence/`, and archived memories.
[Done: 2026-04-23. Deleted `commands/vidux-auto.md`. Scrubbed the remaining active docs/guides references. Updated `scripts/lib/ledger-query.sh` to anchor bimodal windows to the newest ledger entry so the contract tests stay deterministic. Gate: `python3 -m pytest -q` => 136/136 pass.]

#### 10.7 — Dogfood refresh on public docs [completed] [Depends: 10.6] [Agent: codex/claudux-dogfood]

1. Correct docs-site drift against current doctrine: `## Progress` is core, `PROGRESS.md` is optional overlay state when present, and `in_review` remains optional rather than required everywhere.
2. Align the Codex docs with the live static-shim pattern: `automation.toml` + DB row register the automation, while `prompt.md` + `memory.md` live under a shared `<lane-dir>/<lane-id>/` state directory.
3. Preserve the existing VitePress IA and nav while scrubbing stale Leo-specific example paths and review-bot names from public template pages.
[Evidence: README.md:115, docs/guide/index.md:68, docs/concepts/plan-structure.md:58-101, docs/fleet/platforms.md:14-15, docs/fleet/codex-lifecycle.md:12-115, docs/fleet/codex-setup.md:35-216, docs/reference/prompt-template.md:22-287]
[Done: 2026-04-26. Kept the existing docs IA intact while tightening the public Codex pages around shared lane-state files, `execution_environment = "worktree"`, and the shipped `scripts/lib/codex-db.sh` helpers. README + prompt-template examples now reflect the current doctrine. Gate: `npm run docs:build` PASS, `python3 -m unittest tests.test_vidux_contracts tests.test_plan_gc` PASS (153/153), sidebar-link audit PASS.]

## Decisions
(Decision Log — intentional choices that future agents must not undo)
- [DIRECTION] [2026-04-09] vidux-loop.sh is NOT deleted — it still works and vidux-loop.sh stays as optional tooling. But automation prompts no longer require it. The gate is now inline in the prompt.
- [DIRECTION] [2026-04-09] 15 doctrines → 6 principles. The 9 removed are fleet ops (moved to guides/fleet-ops.md and /codex skill).
- [DIRECTION] [2026-04-09] No Redux jargon. No "store", "dispatch", "reduce", "unidirectional flow." Plain English only.
- [DIRECTION] [2026-04-09] COPY SAFETY: Automations must never invent marketing copy. Use only text patterns that exist in the codebase. Product is "StrongYes Pro" with "unlimited AI coaching." No sprints, no founder notes, no day-one plans. Evidence: remote trigger hallucinated copy in commit 5ef4498c.
- [DIRECTION] [2026-04-09] Remote triggers (claude.ai/code/scheduled) are dangerous — they push directly to main with zero review. Prefer Codex worktree model (pushes to branch first). Remote trigger for strongyes disabled.
- [DIRECTION] [2026-04-11] All automation pushes go through draft PRs — NEVER direct-to-main. Draft PRs are the durable, worktree-loss-proof manifest of in-flight work (recoverable via `gh pr list`). Phase 5 implements the cloud-agnostic core. Builds on the 2026-04-09 remote-trigger direction. Closes the Phase 2.4 loop (130 stranded resplit-ios branches with no PR metadata).
- [DIRECTION] [2026-04-26] **Ready-PR-first supersedes draft-first for operational PRs.** Keep the safety boundary at "PR, never direct-to-main," but open ready-for-review by default so configured review bots, preview comments, and CI gates run immediately. Draft is only for true WIP or a missing gate; as soon as the gate passes, run `gh pr ready <N>`. This refines the 2026-04-11 direction without reviving direct-main pushes.
- [DIRECTION] [2026-04-26] **PR-first worktree finalization supersedes merge-back prompts.** Worktree lanes push branch + PR, record the resume point there, then delete or later garbage-collect the local worktree after classification. Direct merge-back-to-main prompts are historical and unsafe at fleet scale; cleanup must distinguish open PR, merged/safe, dirty, closed-unmerged, and no-PR branches before removing anything.
- [DIRECTION] [2026-04-11] vidux core is open-source and cloud-agnostic. Phase 5 contains ONLY draft-PR mechanics — no Greptile, no Sentry, no Nia, no Seer. Paid-service integrations live in `/vidux-codex` scope as composable skills, not in this plan. "Keep side effects like greptile and followups agnostic, that is more a /vidux-codex kinda thing." — Leo.
- [DIRECTION] [2026-04-12] Design skill naming convention: `brand-*` (identity), `craft-*` (platform patterns), `figma-*` (workflow). Renames: strongyes-design→brand-strongyes, picasso→craft-ios, preview-svg-design→craft-svg, figma-implement-design→figma-implement. New: brand-leojkwan. Do not revert these names.
- [DIRECTION] [2026-04-14] Automation recipes may reference specific tools (Greptile, code-reviewer, ledger) as opinionated defaults. This EXPANDS the 2026-04-11 "keep side effects agnostic" direction: the core SKILL.md stays tool-agnostic, but `guides/recipes.md` is explicitly opinionated about "how we work." Recipes are Leo's workflow codified, not generic docs. — Leo: "i want our system with greptile and code reviewers codified, though opinionated in how we work."
- [DIRECTION] [2026-04-22] Explicit Leo override: the `/vidux-auto` breadcrumb window ends early once active prompts/tests are migrated. Delete the deprecated command/skill files; keep only historical mentions in PLAN.md, CHANGELOG.md, evidence, and archived memories.
- [DIRECTION] [2026-04-14] ~~Claude Routines are the primary automation primitive.~~ **SUPERSEDED 2026-04-15:** Routines are cloud-based — vidux core must stay platform-agnostic and local-first. Routines references belong in `/vidux-claude` (platform-specific companion), not in the core SKILL.md or README. CronCreate stays as the local automation primitive. Leo: "delete Routines we dont need it anymore its cloudbase."
- [DIRECTION] [2026-04-15] Merge `/vidux-claude` + `/vidux-codex` + `/vidux-fleet` → single `/vidux-auto` companion. Three skills with 1,998 lines and heavy topic overlap (CronCreate 35x, observer 32x, memory.md 44x across the three). Strip all personal references (~62 total). PR Nurse pattern added to close the PR #338 feedback gap. Two OSS artifacts: `vidux` (core) + `vidux-auto` (automation). Leo: "should we finally look into creating a mega plugin for /vidux to combine all this."
- [DIRECTION] [2026-04-12] Skill consolidation: 54→~42 skills. Vendor research (Anthropic + OpenAI) confirms: "earn your complexity," "eval-driven pruning." Unused skills are noise in the routing table. Tier 1 deletes bulk-import cruft; Tier 2 merges overlapping pairs; Tier 3 needs Leo's call. vidux-skill-refiner cron (20 min) handles ongoing quality.
- [DELETION] [2026-04-15] Phase 7.1.2 (`guides/routines.md`) closed without writing the file. All four scope items — three trigger types, migration from CronCreate, daily limits, cadence planning — are already in `guides/recipes.md` (L5, L11-70 for triggers + key details; L491-502 "Hybrid Strategy: Routines + CronCreate" for migration; L474-489 "Daily Budget Planning" for limits and cadence). Do NOT re-create `guides/routines.md` — a standalone primer would duplicate 90%+ of recipes.md and invite drift (exactly the pattern vidux-improve cycles 1-7 were fixing). If a reader needs routines context, they read recipes.md. One source of truth.
- [DIRECTION] [2026-04-16] Recipes stay platform-agnostic in naming. `guides/recipes.md` may describe opinionated workflows but MUST NOT name specific tools (Greptile, Sentry, code-reviewer agent, Nia, Seer). Use generic phrasing: "If there are automation PR reviews (from review bots, code-review agents, or static-analysis comments), address them before merging." Specific tool wiring belongs in `/vidux-auto` (which is Leo's opinionated stack). This refines the 2026-04-14 "recipes may reference tools" direction — opinionated WORKFLOW yes, specific TOOL NAMES no. Leo: "try to not name tools explicitly like greptile but you say IF there are automation PR review please address before merging them in for example."
- [DIRECTION] [2026-04-16] PR Nurse local-CI check for resplit-ios = `tuist build` + all unit tests locally. The Nurse must not mark a draft PR ready-for-review until local unit tests pass. Resolves Q10. Leo: "local check for resplit ios tuist build unit tests locally all the unit tests would be ideal."
- [DIRECTION] [2026-04-16] T1-T4 Change Classification protects vidux core from churn. Most /insights findings are T1 (prompt) or T2 (CLAUDE.md). Recipes are T3 (companion). Core discipline (T4) only changes when the discipline itself is wrong. /insights report confirmed zero T4 changes across 10 sessions — the five principles are sound. Leo: "we need to have a framework for that... otherwise vidux is gonna keep changing."
- [DIRECTION] [2026-04-16] Codex automations adopt the same static-config pattern as Claude lanes: TOML `prompt` field becomes a thin shim → `~/.codex-automations/<name>/prompt.md`. Edit prompt.md freely without restarting the app. One-time TOML migration, then automations "never move." Leo: "automations point to a static file that we can easily change frequently without having to close codex app."
- [DIRECTION] [2026-04-16] vidux-auto should include a "Recommended CLAUDE.md Rules" section with battle-tested agent hygiene rules (re-read before edit, verify before completing, simple-creative-direct). These are the /insights-derived rules that any vidux user benefits from. Ship as open-source guidance alongside the skill. Leo: "mention CLAUDE.md best practices if you're gonna do this for open source, don't leave any tips behind."
- [DIRECTION] [2026-04-17] Single entry point: `/vidux` alone covers both discipline (Part 1) and automation (Part 2). Users should never pick `/vidux` vs `/vidux-auto` vs `/vidux-codex` vs `/vidux-claude` vs `/vidux-fleet` at invocation time — that's architecture-leaking. Deep automation doctrine lives in `references/automation.md`, loaded on demand from within a /vidux session. The Phase 8 two-skill split was a transitional shape; Phase 10 is the final shape. Leo: "users shouldn't have to pick... it should just be baked in where if user wants an automation the skill knows how to write the best automation and know how of creating the skill for codex and claude local." Companion rule: when future work adds a capability, default to "Part N of /vidux" over "new /vidux-foo sibling skill." Split only when the invocation audience is genuinely different (not just the topic).
- [DELETION] [2026-04-17] 5 companion command files deleted from `commands/` — `vidux-claude.md`, `vidux-codex.md`, `vidux-fleet.md`, `vidux-dashboard.md`, `vidux-manager.md`, `vidux-plan.md`. Do NOT recreate them. Their operational patterns survive in `/vidux` Part 2 and `references/automation.md`. `commands/vidux-auto.md` stays as a 37-line deprecation breadcrumb (90-day window, removal target 2026-07-17) so existing lane prompts that still say `Load: /vidux, /vidux-auto` don't crash during migration. After 2026-07-17, delete `commands/vidux-auto.md` too.
- [DIRECTION] [2026-04-17] **Progress is code change.** A PR that only touches `PLAN.md`, `investigations/`, `evidence/`, or `INBOX.md` without a source-code change is not progress — it is bookkeeping. Bundle plan updates into the code PR that ships the fix, or keep notes local until a fix is ready. Standalone "flip row to [completed]", "reconcile Phase N", "audit already-delivered", or "investigation closeout" PRs are prohibited. If a cycle produces no code, it produces no PR and no commit — notes stay on disk for the next cycle to pick up. Root cause this fixes: at fleet scale, the cheap tasks (flip/reconcile/audit) dominate the PR stream and real bug fixes starve. The doctrine previously said "investigation only — no code" which permitted the pattern; this entry reverses it. Evidence: resplit-ios shipped 15+ consecutive `plan(backlog)` / `docs(investigation)` / `docs(L6) re-verification` PRs across 2026-04-17 while user-reported bugs (flicker, remove-from-live-split silent no-op, guest receipt entry) sat unaddressed for 6+ days. Leo: "all things preventing us from shipping kill the concept... screw the types, reduce types please we dont need extra bokkeeping."
- [DIRECTION] [2026-04-17] **`observed` is a first-class evidence type.** Added to the Evidence section template. User-observed behavior ("flicker on launch in TestFlight build 990", "remove button does nothing during live split") now enters the plan as valid evidence, same standing as codebase grep or PR comment. Previously excluded — lanes could not cite "I opened the app" because the evidence list only allowed document-oriented sources. Fixes the root-cause gap where user observations never entered the system unless a human translated them first. Leo: "the fleet had plenty of bugs that were definitely still there and unaddressed" — confirms the bugs existed but the doctrine had no ingest path for them.
- [DELETION] [2026-04-17] **Observer lane pattern deprecated.** Section 8 (Observer Pairs) in `references/automation.md` collapsed from ~26 lines to a 3-line deprecation notice. Recipe 1 (Fleet Watcher) and Recipe 4 (Observer Pair) in `guides/recipes.md` marked DEPRECATED with ⚠️ blockquote warnings. Section 3 "The observer (the one exception to 'fewer lanes')" rewritten as "Observer lanes are deprecated." Decision tree simplified (observer line removed, total lane count 3-7 → 2-4 for 24/7). Rationale: observers are an orchestration smell — read-only lanes that add memory.md files, cross-lane reads, and cycle offsets without catching bugs the writer couldn't already see in its own logs. Drift belongs upstream (fix the writer's prompt), not in a second scheduled lane. Leo: "fleet watch feels like a code orchestration smell." Observer content kept as historical stubs so cross-refs don't 404.
- [DIRECTION] [2026-04-17] **Autonomous adaptive doctrine patch.** Second round of cuts in the 2.9.0 release: (a) `## Open Questions` and `## Surprises` downgraded to optional sections — questions promote to `[pending]` research tasks or `[Blocker: ...]` task annotations; unexpected findings go into Progress entries. Contract test `REQUIRED_PLAN_SECTIONS` loosened from 8 to 6. (b) 3× stuck rule no longer requires a human — the agent force-switches to another surface; next cycle finds new evidence or task stays blocked. (c) Status FSM: `blocked` is now terminal; no `blocked → pending` reverse transition. A blocked task is replaced, not revived. (d) "No reordering mid-cycle" rule removed — agents re-sort the queue when observed evidence changes priority, noting the reorder in Progress. (e) `[P]` parallel marker removed from queue order (parallel research fan-out still happens via Mode A delegation). (f) L3 investigation escape hatch removed — max two levels (L1 plan, L2 investigation), split into separate L1 plans if deeper decomposition needed. (g) Push authorization compressed from 3-tier ladder to 1 sentence: draft PRs are always safe, direct-to-main/destructive need explicit authorization. (h) Garbage collection thresholds removed (aspirational, never enforced) — agents archive when the plan feels heavy. (i) "Every agent is a worker" standalone section folded into the ACT step of the cycle. (j) Principle 4 gained a one-line addendum: "If evidence changes mid-cycle, the queue re-sorts. You don't need permission to reorder." Net effect: fewer required ceremonies, more agent autonomy, same contract tests. Rationale: Leo asked the doctrine to "support autonomous adaptive work" — every cut in this round replaces a human-gated checkpoint with an agent-owned decision, or deletes a section nobody filled out anyway. Leo: "let's make sure we cut and simplify and support autonomous adaptive work where possible."
- [DIRECTION] [2026-04-18] **Core/recipes split (2.10.0).** Third round: structural refactor. SKILL.md shrinks to Part 1 only (~284 lines: five principles + cycle + PLAN.md template + investigations + course correction). Part 2 (Automation) moves to `guides/automation.md` as an opt-in load — readers encounter core first, automation second. New `guides/recipes/` directory holds 12 tactical recipes (CLAUDE.md rules, lane prompt patterns, same-tool subagent delegation, Codex-native runtime, and 8 /insights-derived friction recipes). Rationale: core vidux must stay opinionated about the discipline (principles + cycle + PLAN.md) but must not opinionate tactics that vary per team or per user. Previously, things like the Mode A compression contract, the 8-block prompt template, and specific Codex registration mechanics all lived inline in core — pushing core toward 500+ lines and making it harder to read for someone who just wants the discipline. Recipes are opt-in; agents load a specific recipe on demand. Leo: "try to put as much 'optimization' that isn't effective in core vidux as a recipe... vidux should be opinionated by default in its machinery but not have customizations like that."
- [DELETION] [2026-04-18] **Cross-tool delegation deprecated (2.10.0).** Mode A / Mode B were previously documented as Claude-primary + Codex-secondary cross-tool handoffs. That pattern created context-loss at the egress boundary, prompt-shim fragility, and state-sync surprises between two runtimes. Modern delegation is same-tool subagent dispatch via the `Agent()` tool — the compression contract and 5-block spec still apply, but parent and subagent share the same runtime. The cross-tool era had measured wins (10–110× Mode A / ~5× Mode B) but the reliability cost at fleet scale exceeded the context savings. `/vidux-codex` skill (in `~/Development/ai`) was already deleted (commit 4534ac5 on 2026-04-17). `guides/recipes/codex-runtime.md` covers native Codex Desktop usage — no cross-tool handoff. `guides/recipes/subagent-delegation.md` replaces the old cross-tool Mode A/B writeup. Leo: "let's kill the concept of vidux codex if there is any we never want cross contamination again, either vidux runs on codex and creates crons their way which we'll give recipes for, or it's all claude no egress or context loss."

## Open Questions
- Q1: Should contract tests track guide files (guides/*.md) or only SKILL.md? -> Action: decide after v3 guides land
- Q2: PR ownership — lane-owned (`gh pr create` per automation, ready by default). **Refined 2026-04-26.**
- Q3: Draft → Ready promotion — lane-owned once the missing gate passes. **Refined 2026-04-26.**
- Q4: Auto-merge — allowed only when repo/overlay authority says so and checks/review findings are green/acked; never merge a draft. **Refined 2026-04-26.**
- Q5: Scope — vidux fleet only; other repos adopt via their own plans. **Confirmed 2026-04-11.**
- Q6: Leo's personal pushes stay as-is (Phase 5 is automation-only). **Confirmed 2026-04-11.**
- Q7: 130 stranded resplit-ios branches left dead. **Confirmed 2026-04-11.**
- Q8: Should vidux-auto live in the vidux repo (`commands/vidux-auto.md`) or as a standalone skill in `~/Development/ai/skills/vidux-auto/SKILL.md`? -> Action: decide during 8.0. Tradeoffs: in-repo means one `git clone` gets everything; standalone means the ai skills repo can version independently.
- Q9: Should `guides/recipes.md` (517 lines, opinionated with tool names) stay in the core repo or move to vidux-auto? **Resolved 2026-04-16.** Strip specific tool names (Greptile, code-reviewer, Sentry). Use generic phrasing: "If there are automation PR reviews (from review bots, code-review agents, or static-analysis comments), address them before merging." Recipes stay in core after scrub.
- Q10: For repos without remote CI (resplit-ios), what local checks should the PR Nurse run? **Resolved 2026-04-16.** `tuist build` + run all unit tests locally (ideal). The Nurse must not mark PR ready until local unit tests pass.

## Surprises
- [2026-04-11] `vidux-core-test` cannot be the Wave 1 pilot — it operates on a non-git experiment directory (`~/Development/vidux-core-test/`) with explicit "NEVER do: `git push` anywhere" in its Authority block. The audit falsely classified it as "push-capable" because the prohibition text matched the grep pattern. Corrected pilot to `strongyes-coach-p0` which pushes directly to origin/main (the exact behavior to replace).
- [2026-04-14] resplit-ios `gh pr create` fails with "shared commit overlaps with an existing PR" — lanes follow the draft-PR prompt (they TRY to create PRs) but `gh` rejects when new branches share commit ancestry with old branches. The 130 stranded branches (Q7: "left dead") may be contributing. Impact: resplit Wave 3 blocked until this is resolved. strongyes unaffected.
- [2026-04-09] v3 rewrite removed 6 PLAN.md sections the contracts enforce. Contract tests caught it immediately.
- [2026-04-09] Remote Claude trigger hallucinated marketing copy ("14-day sprint", "founder notes", "First Bite Labs") while fixing T91/T92. The automation read the plan correctly but invented product concepts. Root cause: no copy safety constraint in prompt. Fix: added COPY SAFETY to writer prompts + reverted bad commit.
- [2026-04-09] Claude Desktop v1.1062.0 migrated from local-agent-mode-sessions/ to claude-code-sessions/. Local scheduled tasks JSON not carried over. Local task creation is UI-only — no programmatic API exists (anthropics/claude-code#41364).

## Progress
- [2026-04-09] Plan created. SKILL-v3.md drafted (220 lines). 4 guides extracted (810 lines). /claude skill created. Remote trigger created then disabled (pushed hallucinated copy to main).
- [2026-04-09] All 12 Codex automations on v3 prompts. 0 vidux-loop.sh refs. resplit-web-ux SHIPPED (CTA fix). codex-watch ran fleet scan. StrongYes T92 shipped (/prep 44→101 companies). Bad copy reverted + COPY SAFETY added. 4 repos synced (0/0).
- [2026-04-09] SKILL.md replaced with v3 (1000→208 lines). 14 contract tests updated. 394 worktree dirs GC'd (33GB freed, disk 2.8→147GB). 38 merged branches deleted. All 4 phases complete — v3 revamp shipped.
- [2026-04-11] Wave 0 tasks 5.0.1 (plan) and 5.0.2 (audit) completed. Audit discovered: 37 total lanes (35 Claude + 2 Codex observers), NOT the 14 stated in Phases 2-4. ~20 are push-capable, 0 create PRs today. Full audit at investigations/draft-pr-flow.md. Codex-to-Claude migration is effectively complete (only 2 Codex observers remain). CronCreate lane `vidux-draft-pr` created (every 15 min, session-only — CronCreate durable mode did not persist to disk). Claude automation prompt written at ~/.claude/automations/vidux-draft-pr/prompt.md. Wave 0 now blocked on: Leo Q2-Q7 answers (5.0.3) and pilot lane decision (5.0.4). Delegation Track + Track B (paid-service skills, sentry cleanup) moved out of this plan per Leo direction — lives in /vidux-codex scope. Good night cycle — cron takes over.
- [2026-04-11] Phase 5 restructured from 3-track (Core + Delegation + Track B) to clean core-only after Leo direction: "vidux is open source — keep side effects agnostic, paid tooling lives in /vidux-codex." Removed Delegation Track (5D.1-5D.5), Track B (5B.1-5B.2), and all Greptile/Sentry/Seer/Nia references from Phase 5 tasks, Decision Log, and Open Questions. Research results preserved at investigations/paid-tooling-pr-integration.md for /vidux-codex to consume. Key research findings: Nia has NO PR surface; Greptile supports drafts via triggerOnDrafts; Seer Code Review hard-skips drafts. Phase 5 now contains 15 tasks across 5 waves (Wave 0 plan+audit → Wave 1 pilot → Wave 2 batch → Wave 3 fleet → Wave 4 gate). 6 Open Questions with provisional answers (Q2-Q7) await Leo's confirm/overturn. Cron and team agents being set up to grind on Phase 5 continuously.
- [2026-04-11] Leak audit clean. Phase 5 opened as draft-PR flow with wave-based rollout strategy. Research dispatched to background Agent. Leo: "this is a huge change up since we've mainly done things local and merged back to main."
- [2026-04-12] Phase 6 opened: skill consolidation 54→42. Design skill renames shipped (4 renames, 1 new brand-leojkwan, 15 cross-refs updated, 0 stale). Nia research confirms vendor guidance: Anthropic says "start minimal, earn complexity," OpenAI says "eval-driven pruning." Tier 1 (8 deletes: hooks, jed, atlas, greenapple, judge0, doc, jupyter-notebook, spreadsheet — all bulk-import cruft with zero lane references). Tier 2 (5 merges: seo+ahrefs-seo, figma+figma-implement, vidux-loop+vidux-recipes, vidux-version+vidux-status→vidux, splitter→pilot). Tier 3 (6 evaluate: codex, multithready, resplit-engineering, imagegen, maily, media-studio+fcp — need Leo). vidux-skill-refiner cron live (20 min, session-only). Next: Leo approves Tier 1+2 cuts, then execute.
- [2026-04-10 04:58 EDT] Overnight quality cycle 1: Fleet scorecard 6 SHIPPING / 4 IDLE / 0 blocked / 0 crashed / 0 mid-zone. SHIPPING: resplit-bug-fixer (re-verifying AJBM/AI4/AJL5 family on build 1648), resplit-code-quality (UITestLaunchConfigurationTests + dead-code prune), resplit-currency (CLF/CNH/FOK/GGP/IMP/JEP/XDR catalog gap), resplit-ios-ux (ja/es-ES/fr-FR locale screenshots, 5 locales remaining), resplit-web-ux (claim tap-target + desktop grid + heading hierarchy), strongyes-ux-scanner (problems metadata fix). IDLE: resplit-launch-loop (1648 already uploaded + distributed), strongyes-backend, strongyes-blog-writer (pivoted to DSA landers, evidence file pending), strongyes-release-train. ASC tracker: 17 fixed / 79 verified / 3 blocked / 0 new — bug-fixer is *correctly* idle-scanning per nurse log; 3 blocked rows (ABv07GVF OCR polling singleton, AFw7znl8 address geocoding, AKigU4Rh OCR key-value extraction) are architecture/eng-design tasks needing human input, not auto-resolvable. Vidux: pushed `f84b53e fix: align gate test with worker-first model` to origin/main (was 1 ahead); uncommitted v3 cleanup (-1834 lines: SKILL-v3 drafts + guides/vidux/* legacy guides + DOCTRINE/SKILL/commands/vidux.md consolidation) left untouched as in-progress sibling work. Flagged: `test_checkpoint_accepts_untracked_matching_process_fix_artifact` is a pre-existing flake — hangs at 10s subprocess timeout under pytest's capture_output but completes in 1-2s under raw subprocess.run; not caused by v3 cleanup, exists at HEAD.
- [2026-04-14] Self-improvement cron complete (10 items, 4 cycles, commits 01cb9c2→206b6cd): README Mode B diagram, fleet pattern refresh, comparison table fix, Lessons from Production section, claudux alignment, mermaid render fix. Cron cancelled after 2 IDLE checkpoints. Wave 2 observer audit (5.2.3): strongyes PASS (draft PRs working, Leo promoting), resplit-ios BLOCKED (gh pr create shared-commit overlap). Next: investigate resplit gh overlap issue before Wave 3.
- [2026-04-15] Phase 7.1.1 closed: guides/recipes.md verified complete (517 lines, 8 recipes via `grep -c '^## Recipe'`, Routines primer integrated L11-70 — the primer-separate-guide 7.1.2 is now likely redundant, next cycle to decide). Next: 7.1.2 decision (write guides/routines.md vs close-with-Decision-Log).
- [2026-04-15] Phase 7.1.2 closed as redundant. Decision Log [DELETION] added. Verification grep on recipes.md confirmed all four scope items (triggers, migration, daily limits, cadence) already present. Single source of truth preserved. Next: 7.1.3 (commands/vidux-fleet.md — replace Codex automation.toml references with Routines).
- [2026-04-15] Phase 7.1.3 shipped: commands/vidux-fleet.md now leads with Claude Routines (primary) via `/schedule`, CronCreate lanes second, Codex automation.toml relabeled legacy. Added `--target routine|claude-lane|codex-legacy` flag to `write` subcommand (routine is default). Discover/inventory/audit scan paths prioritize routines → claude-lanes → codex-legacy. Cross-refs to recipes.md L11-70 and L491-502 verified. Next: 7.1.4 (README.md Fleet Intelligence section).
- [2026-04-15] Phase 7.1.4 shipped: README.md Fleet Intelligence section now explicitly names the three trigger types + primitive priority (Routines primary → CronCreate → Codex legacy) + direct anchor links to recipes.md #how-routines-work and #hybrid-strategy-routines--croncreate. Also removed stale `guides/routines` directory reference (left over from 7.1.2 closure). Next: 7.1.5 (SKILL.md — add Routines as first-class primitive alongside CronCreate).
- [2026-04-15] Course correction: stripped Routines from core (cloud-based, not platform-agnostic). 7.1.5 blocked. Commit 3ac3193.
- [2026-04-15] Phase 8 planned: merge vidux-claude (619L) + vidux-codex (626L) + vidux-fleet (753L) → single vidux-auto companion (~800-1000L after dedup + scrub). 10 tasks across 3 sub-phases (audit → migrate → verify). PR Nurse pattern (Recipe 9) added to close the feedback gap (PR #338 evidence: P1 from Greptile unaddressed, merged anyway). 3 new Open Questions (Q8-Q10). Decision Log [DIRECTION] entry added. Next: 8.0 content audit.
- [2026-04-16] Q9 + Q10 resolved. Q9: strip tool names from recipes.md (generic "automation PR reviews" phrasing). Q10: resplit-ios PR Nurse local CI = `tuist build` + all unit tests. Two new [DIRECTION] entries added so Phase 8 executors see the contract. Q8 (vidux-auto location) still open.
- [2026-04-16] Investigated session JSONL growth (current session 64 MB / 47K lines). Root cause: Vercel plugin's universal `PreToolUse` hooks on Read|Edit|Write|Bash fire 14.5K times per session and each writes an empty-response `async_hook_response` attachment (~744 B each = 10.8 MB wasted). Combined with `hook_success` spam (8 MB), Vercel plugin accounts for 30% of session bytes on a non-Vercel session. Evidence: /Users/leokwan/Development/leojkwan/evidence/2026-04-16-session-jsonl-growth.md. Memory updated: reference_session_bloat_anatomy.md. Recommended fix: toggle `vercel@claude-plugins-official: false` when not doing Vercel work, cycle session at 40 MB.
- [2026-04-16] Phase 9 planned: Fleet Intelligence & Stability. Three-agent swarm investigated Codex config (13 automations, dual TOML+SQLite storage, static-file indirection feasible), Codex GC (4 GB at ~/.codex/, top target: logs_2.sqlite 474 MB + archived_sessions 2.7 GB), and /insights classification (10 sessions, 5 friction types, zero T4 changes needed). T1-T4 change framework added to Decision Log. 4 T2 rules applied to ~/.claude/CLAUDE.md immediately (Edit hygiene, verify-before-complete, simple-creative-direct, Tailwind gate). 7 tasks planned (9.0-9.6).
- [2026-04-16] Phase 9 v2 after review. Two review agents scrutinized v1. Changes: (1) CUT insights aggregator script + 2h cron — replaced with manual triage process ("after every 10 sessions, review facets/"), build script only when painful. (2) CUT dedicated codex-gc lane — fold into existing fleet-watcher. (3) SIMPLIFY Codex config migration to 3 highest-churn automations only (rest are legacy). (4) ADDED `guides/agent-config-rules.md` — 3 platform-agnostic rules for OSS (re-read before edit, re-read after fail, proportional response). Cross-refs Principle 5 for verification. (5) TRIMMED recipes from 6 to 3 (kept battle-tested, dropped horizon ideas). Tasks: 7→6 (9.0-9.5). Next: Leo review, then execute 9.0+9.2 in parallel with Phase 8.
- [2026-04-16] Phase 8.0 completed: content audit + migration map. Read all 1,998 lines across vidux-claude (619L), vidux-codex (626L), vidux-fleet (753L). Classified every section as CORE/AUTO/PERSONAL/DEAD/OVERLAP. Results: 72 personal refs found (vs 62 estimated — delta from deeper path/lane-name scrub), ~280 DEAD lines (14% of source, mostly Routines refs + deprecated Codex fleet + old activation/related-skills sections), 11 overlap resolutions documented (observer pairs: codex primary; delegation: codex primary; 24/7 model: claude primary; prompt structure: keep both spec+templates). Proposed 20-section TOC for vidux-auto. Estimated size: ~1,180L pre-compression → 900-1000L target with aggressive editing in 8.2-8.5. Evidence: `evidence/2026-04-16-auto-migration-map.md`. Next: 8.1 (create vidux-auto skeleton).
- [2026-04-16] Phase 8.1 completed: created `commands/vidux-auto.md` skeleton (~190 lines). 20 sections from migration map TOC, each with header + 1-2 sentence description + `<!-- SOURCE: vidux-claude Lxx-yy -->` comments pointing to source material. Cross-references `guides/agent-config-rules.md`, `guides/recipes.md`, `guides/draft-pr-flow.md`, `guides/fleet-ops.md` instead of inlining. Zero personal references — uses generics throughout. Section 18 (Insights Triage) added from Phase 9.4 to complete the operational picture. Ready for 8.2-8.5 content migration. Next: 8.2 (migrate session management), 8.3 (lane management), 8.4 (delegation), 8.5 (fleet ops).
- [2026-04-16] Phase 8.3 completed: migrated + scrubbed lane management and 3 additional vidux-claude sections into vidux-auto. Filled Section 3 (Lane Management: decision tree, coordinator pattern with 5 rationale bullets genericized from "Leo opens ONE memory.md" to "the operator opens ONE memory.md", observer intro with when-to-add heuristic, 6-lane hard cap with measured JSONL/worktree evidence, 5 anti-patterns, ghost lane detection, polish-brake trigger — stripped "leojkwan" from measurement example). Filled Section 10 (Prompt File Structure: disk-authority rationale, 8-block spec, <=15 line harness rule — dropped "A/B against Codex" paragraph as DEAD). Filled Section 12 (Creating/Updating/Deleting Lanes: 5-step create workflow, cadence table with 15-min RETIRED note, >=8 min stagger rule, update banner genericized from "Leo direct" to plain date, delete with archive-not-hard-delete). Filled Section 13 (Memory Files: entry format from vidux-claude L336-362, dual-token delegation checkpoint from vidux-codex L432-439, reset markers, last-10 visibility). File grew 387->550 lines. `grep -i personal-refs` returns 0 hits. Remaining skeleton sections: 4, 5, 6, 8, 11, 16 for Phases 8.4-8.5.
- [2026-04-16] Phase 8.2 completed: migrated + scrubbed session management and 5 additional vidux-claude sections into vidux-auto. Filled Section 1 (24/7 Fleet Model: lane/session diagram, hot/cold storage table, cloud scheduling rejection — genericized "Leo rotates 4 accounts" to "multi-account rotation"), Section 2 (Session Management: JSONL growth anatomy table, 3 GC levels, session-gc lane spec with tunable 40-80 MB threshold, cycle signal, plan-GC-is-coordinator's-job rule — stripped "Leo reads the signal" to "the human reads"), Section 7 (Concurrent-Cycle Hazards: 3 verified production bugs + 4-line prevention checklist — verbatim, no personal refs), Section 9 (Worktree Discipline: isolation rules, symlink deps, lint-staged gotcha — genericized strongyes-web paths to `<project>`), Section 14 (Lean Dispatch: 7 prioritized rules — stripped "Leo direct" attribution, genericized "Leo has 4" to multi-account), Section 15 (Deferred Tool Loading: ToolSearch prerequisite pattern). File grew 252→387 lines. `grep -i personal-refs` returns 0 hits. Remaining skeleton sections (3, 4, 5, 6, 8, 10-13, 16) still have placeholder descriptions for 8.3-8.5 to fill. Next: 8.3 (lane management).
- [2026-04-16] Phase 8.4 completed: migrated + scrubbed delegation modes from vidux-codex into vidux-auto. Filled Section 4 (Delegation Mode A + Mode B: flow diagrams genericized from "Claude/Codex" to "primary/secondary model", cost shift table, full decision tree with tier-based thresholds, tier math table preserving 10.1x/49.4x/109.7x savings ratios, compression contract verbatim, 5-block implementation prompt shape, 7-step diff-review checklist, invocation mechanics without tool-specific flags, 9 execution rules). Filled Section 8 (Observer Pairs: what observers catch with evidence patterns from delegation studies, setup recipe with cadence offset/authority discipline/verdict format, when-to-add heuristic, why-secondary-model rationale). Filled Section 11 (Composition Recipes: 6 recipes expanded from bullet list to full patterns — vidux->delegated, delegation+amplifier, delegation+research-agent, Agent parallelism, Agent wrapper for long crons with rule-of-thumb table, qa-iterator with setup/hard-rules). Filled Section 16 (External Tool Pairing: research agent pairing with 16.5x savings, deep-mode hallucination warning, prompt amplifier pairing with when-to-use criteria). File grew 550->811 lines. `grep -i personal-refs` returns 0 hits. `grep -i codex` returns 1 hit (intro mentioning former skill names — appropriate context). Remaining skeleton sections: 5, 6 for Phase 8.5.
- [2026-04-16] Phase 8.5 + 8.6 completed: migrated fleet operations and PR lifecycle into vidux-auto. Filled Section 5 (Fleet Operations: 6 subsections — Discover+Slot Map with generic `<project>` example, Prompt Templates as compact 4-role table referencing guides/fleet-ops.md for full templates, Bimodal Quality Model, 9-check Validation Rubric table with severity levels, Prescription heuristics table with 6 recipe mappings referencing guides/recipes.md, 9 Hard Rules). Filled Section 6 (PR Lifecycle: 3 subsections — Triage at cycle start with `gh pr list` command, PR Nurse 5-step responsibilities integrated into writer lane not separate lane, Self-review before push checklist). All personal refs scrubbed (L369 "the operator is heads-down" genericized from original, L436 "operator says deep work" genericized). File grew 811->913 lines. `grep -i personal-refs` returns 0 hits. All skeleton SOURCE comments replaced with migrated content. Phase 8 content migration complete (8.2-8.6 done). Remaining: 8.7 (core ref updates), 8.8 (deprecation markers), 8.9 (verify+gate).
- [2026-04-16] Phase 8.7-8.9 completed — Phase 8 (vidux-auto merge) is DONE. 8.7: updated core references — SKILL.md companion skills section (2 skills → 1 /vidux-auto), README.md ecosystem table (3 rows → 1), README.md Platform Automation section rewritten, 3 guides/ cross-refs fixed (harness.md, draft-pr-flow.md, recipes.md). 8.8: deprecation markers added to vidux-claude SKILL.md, vidux-codex SKILL.md, and vidux-fleet command (blockquote format, 90-day retention). 8.9: gate passed — 141/144 tests pass (3 pre-existing), 0 personal refs in vidux-auto, 913 lines (under 1,000), all guide cross-refs resolve, all 3 spot-checked operational patterns present (observer pairs, delegation, coordinator). Phase 8 summary: 1,998 lines across 3 skills → 913 lines in 1 vidux-auto companion. 72 personal refs removed. PR Nurse pattern added. Two clean OSS artifacts: vidux (core) + vidux-auto (automation).
- [2026-04-18T19:55Z] **Plan reconciliation sweep.** Audited all 10 phases + 3 sibling projects (`projects/*/PLAN.md`) + ASK-LEO.md + open PRs. Findings: Phase 6 [in_progress]→[completed] (all 17 sub-items done 2026-04-12), Phase 7 [in_progress]→[completed] (all 5 sub-items done 2026-04-15/16), Phase 8 [pending]→[blocked: superseded by Phase 10]. **Real remaining vidux-core work = Phase 5 Wave 3+4 only** (4 pending tasks blocked on resplit `gh pr create` overlap from Phase 2.4 stranded branches). Active sub-project: `projects/vidux-leo-split/PLAN.md` (10 MVP tasks, ~2.3h AI) which ships PR #26 + #27 via a new personal-overlay skill `/vidux-leo` (resolves ASK-LEO Q1 + Q2). Archive-ready: `projects/docs-simplify/PLAN.md` (all 8 tasks [completed]). Out-of-scope: `projects/claudux-evolution/` (3 pending, different tool). Next: execute `projects/vidux-leo-split/` Phase 1 on approval — Leo 19:45Z *"we have a preference on blah blah greptile"* = explicit direction to extract Leo-specific review-gate policy into overlay.
- [2026-04-17] Phase 10 (all 5 subtasks) shipped in commit `8c1f593` + sibling ai commit `44c09a1`. Collapsed `/vidux` + `/vidux-auto` two-skill split into single `/vidux` entry with progressive disclosure. SKILL.md 365L → 498L (Part 1 Discipline unchanged + Part 2 Automation inline). `references/automation.md` NEW (~990L, absorbed Phase 8 vidux-auto body). `commands/vidux-auto.md` replaced with 37-line deprecation breadcrumb (removal target 2026-07-17). 5 orphaned command files deleted (`vidux-claude`, `vidux-codex`, `vidux-fleet`, `vidux-dashboard`, `vidux-manager`, `vidux-plan`). 13 docs/guides cross-refs updated. Net -2,193 lines across 19 files. All remaining grep hits for deprecated names are intentional (breadcrumb + historical PLAN/ARCHIVE/evidence). Plan gate: git status clean, origin/main pushed, `~/Development/ai/skills/vidux/` symlink means OSS change is already live on this machine. **Plan state this cycle:** all Phase 5-10 tasks either `[completed]` or blocked on the known resplit `gh pr create` overlap (Wave 3/4 still parked). No mergeable PRs on vidux repo. Next: if resplit gh overlap gets resolved externally, Wave 3 unblocks; otherwise this plan is mostly cold — candidate for an archive pass when Phase 5 closes.
- [2026-04-22] **2.17.0 — dead-weight kill + personal-ref scrub.** Team doc-review (3 parallel code-reviewers) + `codex review --uncommitted` found 20+ personal refs leaking into core docs and 3 internal contradictions. Shipped: coordinator cadence harmonized to every hour (§5.6 rule 7 + L389 example), `~/.claude-automations/` → `<lane-dir>/` across 23 refs, Leo lane names in §8.5 peer-drift example → `<project>-*` templates, Routines mention scrubbed from L41, Framing B / Codex-unlimited bullet removed, observer tombstone at §8 deleted (superseding the 2026-04-17 "keep as cross-reference stub" direction — cross-refs in CHANGELOG.md updated for the new 2.17.0 entry), §17/§18 stub sections deleted. VERSION bumped 2.16.0 → 2.17.0. CHANGELOG entry documents all changes + flags the deprecated Fleet Watcher recipe's "every 2 hours" as historical-record-left-alone. 133/136 contract tests pass; 3 failures verified pre-existing. Companion `/vidux-leo` + `/pilot` edits in ai repo `54b4124`.
- [2026-04-23T01:40Z] Removed the deprecated `/vidux-auto` command breadcrumb (`commands/vidux-auto.md`) after scrubbing remaining active references in guides/docs and updating contracts to only require `/vidux`. Ledger bimodal tests now use relative timestamps so they stay time-window stable. Gate: 136/136 contract tests pass.
- [2026-04-23T01:50Z] PR nurse pass for the `/vidux-auto` purge branch. Added Phase 10.6 to record the final cleanup, anchored `ledger_bimodal_distribution` to the newest ledger event so offline fixtures stay deterministic, and cleared the repo-wide ShellCheck blockers in the CI-scanned scripts (source directives, quoting, dead locals, no-op truncation). Gate: `shellcheck` passes on the scanned scripts and `python3 -m pytest -q` passes (136/136). Next: push the branch and let PR checks rerun.
- [2026-04-17] **Doctrine patch: kill metadata-only PRs + deprecate observer lanes.** Triggered by Leo's diagnosis of resplit-ios fleet-drift pattern — 15+ consecutive plan-flip / audit / investigation PRs while user-visible bugs sat untouched for a week. Branch `claude/vidux-kill-metadata-prs`. Edits span 9 files, net −19 lines: SKILL.md Principle 3 rewritten, Principle 5 adds "Progress is code change" rule, Evidence section adds `observed` as a first-class source type, Worked Example Stage 1 rewritten ("no PR opens yet"), Status FSM language softened, 4 echoes of "investigation only — no code" replaced. LOOP.md `Every cycle MUST produce a checkpoint commit, even if no code changed` inverted. references/automation.md Section 8 collapsed to a deprecation notice, Section 3 observer subsection rewritten, decision tree simplified (total lanes 3-7 → 2-4 for 24/7). guides/recipes.md Recipe 1 Fleet Watcher + Recipe 4 Observer Pair marked DEPRECATED. docs/concepts/cycle.md + principles.md + plan-fields.md + ARCHITECTURE.md mirror updates. Three Decision Log entries added above. PR opens next.
- [2026-04-26 16:16 EDT] Ready-PR doctrine correction. Core `SKILL.md`, docs/templates, recipes, and automation references now say operational PRs open ready-for-review by default; draft is only WIP/missing-gate. Preserved historical `guides/draft-pr-flow.md` path but rewrote it as Ready-PR Flow. Next: publish as 2.19.0 and let downstream `vidux-leo` continue enforcing auto-merge authority.
- [2026-04-26 19:32 EDT] 10.7 completed. Public docs dogfood pass stayed narrow: README + docs/guide now describe `## Progress` as the core append-only log with `PROGRESS.md` as optional overlay state, and the public Codex pages now match the shipped lane model (`automation.toml` + DB row registration, `prompt.md` + `memory.md` in a shared lane dir, `execution_environment = "worktree"`, `scripts/lib/codex-db.sh` helpers). The prompt-template page also dropped the last hard-coded runtime/session examples. Gate: `npm run docs:build` PASS, `python3 -m unittest tests.test_vidux_contracts tests.test_plan_gc` PASS (153/153), sidebar-link audit PASS. Background `claudux update` shells for this prompt were still present, but they were idle (0% CPU, no docs writes in the last 10 min), so this pass treated them as stale hung workers rather than a live competing writer.
- [2026-04-26 20:50 EDT] 5.3.0 completed. Added `scripts/vidux-worktree-gc.py` to make PR-first local worktree cleanup explicit and classifiable: `primary`, `open_pr`, `merged_clean`, `dirty`, `closed_unmerged`, `unmerged_no_pr`, `unknown`. Updated fleet doctrine away from direct merge-back prompts and documented read-only/default cleanup flow in `SKILL.md` + README. Gate: `python3 -m unittest tests.test_worktree_gc tests.test_plan_gc tests.test_vidux_contracts` PASS (156/156). Dogfood read-only scan on vidux found 45 local worktrees: 27 `merged_clean` removable, 7 `dirty`, 7 `closed_unmerged`, 3 `unmerged_no_pr`, 1 `primary`; no removals performed.
<!-- 1 tasks archived to ARCHIVE.md -->
