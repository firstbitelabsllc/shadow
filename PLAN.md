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


### Phase 5: Draft-PR architecture [in_progress]

**Goal:** All automation pushes go through draft PRs, never direct-to-main. Draft PRs are the **durable source-of-truth for in-flight work** — if a local worktree dies, `gh pr list` is the recovery manifest. Each PR carries: automation id, plan task id, last pushed diff, and the resume point. Closes the Phase 2.4 loop (130 stranded resplit-ios branches with no PR metadata). Formalizes the 2026-04-09 remote-trigger direction. Eliminates the COPY SAFETY-class incident (5ef4498c) by forcing human review.

**Scope (Leo 2026-04-11):** This is a huge change up — every automation today works local-worktree → branch-push → merge-back-to-main. Phase 5 rolls out incrementally in waves.

**Side effects are agnostic (Leo 2026-04-11):** This plan covers ONLY the cloud-agnostic draft-PR mechanics. Paid-service integrations (Greptile review, Sentry context, Seer fixes, Nia indexing) live in `/vidux-codex` scope as composable skills bolted on after the core works. Core ships independently. Research: `investigations/paid-tooling-pr-integration.md`.

**Rollout (wave-based, reversible at every step):**
1. **Wave 0 — Plan + audit.** Lock the plan, audit current push behavior, Leo answers open Qs. No production changes.
2. **Wave 1 — Reference implementation.** Convert ONE low-stakes automation to draft-PR-first. Prove it works for one full production cycle. Document lessons in `guides/draft-pr-flow.md`.
3. **Wave 2 — Batch.** Apply the reference to 3-4 more lanes. Mix shipping + idle.
4. **Wave 3 — Full fleet.** All push-capable automations on draft-PR flow.
5. **Wave 4 — Lock the gate.** Branch protection rejects direct-main pushes from automation actors. Never before Wave 3 completes.

Every wave boundary is reversible. Leo gates each transition.

#### Wave 0 — Plan + audit [completed]
- [completed] 5.0.4 Wave 1 pilot: **`strongyes-coach-p0`**. Original pick `vidux-core-test` is invalid — it operates on a non-git experiment dir with explicit "NEVER git push" in its Authority block. Corrected to `strongyes-coach-p0`: currently pushes directly to origin/main (the exact behavior to replace), StrongYes is smaller than Resplit (lower blast radius), lane is P0-active so it exercises real production cycles. [Corrected: 2026-04-11, see Surprise]

#### Wave 1 — Reference implementation [completed]
- [completed] 5.1.1 Modified `~/.claude/automations/strongyes-coach-p0/prompt.md`: ACT section changed from "merge to main" to "push branch + draft PR". PUSH POLICY replaced: 5-step flow (push branch → `gh pr create --draft` → never direct-to-main → sync main each cycle → fallback on `gh` failure). PR body template carries lane id, plan task, resume point. [Done: 2026-04-11]
- [completed] 5.1.2 Draft-PR mechanics validated end-to-end on vidux repo (leojkwan/vidux#4). Branch push → `gh pr create --draft` → `gh pr list` (visible, isDraft: true) → close + cleanup. coach-p0 plan was CLOSED (no work to ship), so tested directly instead. Friction: zero — `gh` CLI worked cleanly. Surprise: coach-p0 can't be the production pilot (plan closed); need a lane with active work for Wave 2. [Done: 2026-04-12]
- [completed] 5.1.3 Wrote `guides/draft-pr-flow.md` — cloud-agnostic core doctrine: the 5-step flow, branch naming convention, PR body template, recovery via `gh pr list`, fallback on `gh` failure, adoption snippet for lane prompts. [Done: 2026-04-12]

#### Wave 2 — Batch rollout (3 lanes) [completed]
- [completed] 5.2.1 Picked 3 lanes with active plans: `strongyes-backend-trust` (26p+25ip, high-vol), `strongyes-blog-pipeline` (8p, content), `resplit-revamp-executor` (12p+1ip, iOS shipping). [Done: 2026-04-12]
- [completed] 5.2.2 Applied draft-PR pattern from `guides/draft-pr-flow.md` to all 3 lane prompts: ACT sections updated (no merge to main, push branch + draft PR), PUSH POLICY replaced with 5-step flow, fallback on `gh` failure. [Done: 2026-04-12]
- [completed] 5.2.3 Observer-pair audit. strongyes lanes PASS (PR #283 open DRAFT, 10+ merged today by Leo). resplit-ios BLOCKED: `gh pr create` fails 4x with "shared commit overlaps with an existing PR" — lanes are following the draft-PR prompt but `gh` rejects when new branches share ancestry with old branches/PRs. [Done: 2026-04-14]

#### Wave 3 — Full fleet
- [pending] 5.3.1 Remaining ~10 automations. [Depends: Wave 2 complete ✓ — but resplit `gh pr create` overlap issue must be solved first for resplit lanes]
- [pending] 5.3.2 Validate `gh pr list` shows in-flight PR per active lane. [Depends: 5.3.1]

#### Wave 4 — Lock the gate
- [pending] 5.4.1 Branch protection: reject direct-main pushes from automation actors, preserve human pushes. [Depends: Wave 3 complete]
- [pending] 5.4.2 Smoke test both paths. [Depends: 5.4.1]

### Phase 6: Skill consolidation — 54 → ~42 skills [in_progress]

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

### Phase 7: First-Class Automation Recipes + Claude Routines [in_progress]

**Goal:** Upgrade vidux's automation layer from CronCreate/Codex automations to Claude Routines. Codify opinionated, ready-to-deploy recipes for common patterns. Make automation a first-class part of vidux, not an afterthought. Include Greptile-powered PR review and code-reviewer pipelines.

**Why now:** Claude Routines shipped 2026-04-14 (research preview). Cloud-native, persistent, three trigger types (scheduled, API, GitHub events). Supersedes session-scoped CronCreate and the old `claude.ai/code/scheduled` triggers. This is the upgrade path.

**Evidence:**
- [Source: claude.com/blog/introducing-routines-in-claude-code] Routines: scheduled (cron), API (POST /fire), GitHub events (webhooks). Pro=5/day, Max=15/day.
- [Source: 2026-04-14 fleet run] CronCreate lanes die when session closes. Routines survive across sessions.
- [Source: Leo 2026-04-14] "i want our system with greptile and code reviewers codified, though opinionated in how we work"
- [Source: PLAN.md Phase 5] Draft-PR flow is the safety layer. Recipes build on top of it.
- [Source: guides/fleet-ops.md] Existing fleet patterns (gates, observers, coordinators) need Routines-native rewrites.

#### 7.1 — Recipes guide [in_progress]
- [completed] 7.1.1 Write `guides/recipes.md` — 8 opinionated recipes with full prompt templates, trigger configs, and when-to-use guidance. Recipes: Fleet Watcher, PR Reviewer (Greptile + code-reviewer), Draft-PR Lifecycle, Observer Pair, Deploy Watcher, Trunk Health, Skill Refiner, Self-Improvement Loop. [Done: 2026-04-15 — 517 lines, all 8 recipes present (verified grep -c "^## Recipe"), Routines primer integrated at L11-70]
- [completed] 7.1.2 Write `guides/routines.md` — Closed as redundant. All four scope items (three trigger types, migration from CronCreate, daily limits, cadence planning) are already in guides/recipes.md: "How Routines Work" L11-70 (triggers + key details), "Hybrid Strategy: Routines + CronCreate" L491-502 (migration), "Daily Budget Planning" L474-489 (limits + cadence). A separate routines.md would duplicate 90%+ of recipes.md and invite drift. See Decision Log 2026-04-15.
- [completed] 7.1.3 Update `commands/vidux-fleet.md` — Routines as primary primitive, Codex automation.toml marked legacy. [Done: 2026-04-15 — surgical edit: top description, discover/inventory/audit scan paths, `create` config section (Claude Routine primary → CronCreate lane → Codex legacy), `write` subcommand adds `--target routine|claude-lane|codex-legacy` flag with routine as default. Cross-ref `guides/recipes.md` L11-70 (Routines primer) and L491-502 (Hybrid Strategy). File grew 728→753 lines.]
- [completed] 7.1.4 Update README.md Fleet Intelligence section — mention Routines + link to recipes guide. [Done: 2026-04-15 — added Routines primitive priority (scheduled/GitHub/API) + direct anchor links to recipes.md #how-routines-work and #hybrid-strategy-routines--croncreate. Also cleaned stale `routines` reference in guides/ table (was pointing at the now-closed 7.1.2 file).]
- [blocked] 7.1.5 ~~Update SKILL.md — add Routines as first-class automation primitive.~~ **Direction reversed 2026-04-15:** Routines are cloud-based, vidux core stays local-first and platform-agnostic. SKILL.md already mentions CronCreate and companion skills — no Routines addition needed. Instead: strip Routines references from README.md and guide files added during Phase 7.

### Phase 8: Consolidate companion skills into `/vidux-auto` + PR Nurse pattern [pending]

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

#### 8.7 — Update vidux core references [pending] [Depends: 8.2, 8.3, 8.4, 8.5, 8.6]

1. Update SKILL.md "Automation is platform-specific" section: replace `/vidux-claude` + `/vidux-codex` references with `/vidux-auto`.
2. Update README.md ecosystem table: one `/vidux-auto` row instead of three.
3. Update README.md Fleet Intelligence section: point to vidux-auto for mechanics.
4. Update any `guides/` cross-references that point to old skill names.

#### 8.8 — Deprecation markers [pending] [Depends: 8.7]

1. Add `deprecated: true` frontmatter + pointer to vidux-auto at the top of:
   - `~/Development/ai/skills/vidux-claude/SKILL.md`
   - `~/Development/ai/skills/vidux-codex/SKILL.md`
   - `~/Development/vidux/commands/vidux-fleet.md`
2. Do NOT delete the old files — they stay as migration breadcrumbs for 90 days (GC per PLAN.md rules).
3. Update skill symlinks to point to vidux-auto.

#### 8.9 — Verify + gate [pending] [Depends: 8.7, 8.8]

1. Run `python3 -m pytest tests/` — all 142 non-flaky tests must pass.
2. Verify every cross-reference in vidux-auto resolves (file paths, line numbers, guide anchors).
3. Verify no personal references survive: `grep -i "leo\|strongyes\|resplit\|leojkwan\|snowcube\|snap\b\|nicole\|pickles" commands/vidux-auto.md` returns 0 hits.
4. Verify vidux-auto is ≤ 1,000 lines (the merge should SHRINK from 1,998 by removing overlap and personal content).
5. Spot-check: pick 3 operational patterns from the old skills, verify they exist in vidux-auto.

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

## Decisions
(Decision Log — intentional choices that future agents must not undo)
- [DIRECTION] [2026-04-09] vidux-loop.sh is NOT deleted — it still works and vidux-loop.sh stays as optional tooling. But automation prompts no longer require it. The gate is now inline in the prompt.
- [DIRECTION] [2026-04-09] 15 doctrines → 6 principles. The 9 removed are fleet ops (moved to guides/fleet-ops.md and /codex skill).
- [DIRECTION] [2026-04-09] No Redux jargon. No "store", "dispatch", "reduce", "unidirectional flow." Plain English only.
- [DIRECTION] [2026-04-09] COPY SAFETY: Automations must never invent marketing copy. Use only text patterns that exist in the codebase. Product is "StrongYes Pro" with "unlimited AI coaching." No sprints, no founder notes, no day-one plans. Evidence: remote trigger hallucinated copy in commit 5ef4498c.
- [DIRECTION] [2026-04-09] Remote triggers (claude.ai/code/scheduled) are dangerous — they push directly to main with zero review. Prefer Codex worktree model (pushes to branch first). Remote trigger for strongyes disabled.
- [DIRECTION] [2026-04-11] All automation pushes go through draft PRs — NEVER direct-to-main. Draft PRs are the durable, worktree-loss-proof manifest of in-flight work (recoverable via `gh pr list`). Phase 5 implements the cloud-agnostic core. Builds on the 2026-04-09 remote-trigger direction. Closes the Phase 2.4 loop (130 stranded resplit-ios branches with no PR metadata).
- [DIRECTION] [2026-04-11] vidux core is open-source and cloud-agnostic. Phase 5 contains ONLY draft-PR mechanics — no Greptile, no Sentry, no Nia, no Seer. Paid-service integrations live in `/vidux-codex` scope as composable skills, not in this plan. "Keep side effects like greptile and followups agnostic, that is more a /vidux-codex kinda thing." — Leo.
- [DIRECTION] [2026-04-12] Design skill naming convention: `brand-*` (identity), `craft-*` (platform patterns), `figma-*` (workflow). Renames: strongyes-design→brand-strongyes, picasso→craft-ios, preview-svg-design→craft-svg, figma-implement-design→figma-implement. New: brand-leojkwan. Do not revert these names.
- [DIRECTION] [2026-04-14] Automation recipes may reference specific tools (Greptile, code-reviewer, ledger) as opinionated defaults. This EXPANDS the 2026-04-11 "keep side effects agnostic" direction: the core SKILL.md stays tool-agnostic, but `guides/recipes.md` is explicitly opinionated about "how we work." Recipes are Leo's workflow codified, not generic docs. — Leo: "i want our system with greptile and code reviewers codified, though opinionated in how we work."
- [DIRECTION] [2026-04-14] ~~Claude Routines are the primary automation primitive.~~ **SUPERSEDED 2026-04-15:** Routines are cloud-based — vidux core must stay platform-agnostic and local-first. Routines references belong in `/vidux-claude` (platform-specific companion), not in the core SKILL.md or README. CronCreate stays as the local automation primitive. Leo: "delete Routines we dont need it anymore its cloudbase."
- [DIRECTION] [2026-04-15] Merge `/vidux-claude` + `/vidux-codex` + `/vidux-fleet` → single `/vidux-auto` companion. Three skills with 1,998 lines and heavy topic overlap (CronCreate 35x, observer 32x, memory.md 44x across the three). Strip all personal references (~62 total). PR Nurse pattern added to close the PR #338 feedback gap. Two OSS artifacts: `vidux` (core) + `vidux-auto` (automation). Leo: "should we finally look into creating a mega plugin for /vidux to combine all this."
- [DIRECTION] [2026-04-12] Skill consolidation: 54→~42 skills. Vendor research (Anthropic + OpenAI) confirms: "earn your complexity," "eval-driven pruning." Unused skills are noise in the routing table. Tier 1 deletes bulk-import cruft; Tier 2 merges overlapping pairs; Tier 3 needs Leo's call. vidux-skill-refiner cron (20 min) handles ongoing quality.
- [DELETION] [2026-04-15] Phase 7.1.2 (`guides/routines.md`) closed without writing the file. All four scope items — three trigger types, migration from CronCreate, daily limits, cadence planning — are already in `guides/recipes.md` (L5, L11-70 for triggers + key details; L491-502 "Hybrid Strategy: Routines + CronCreate" for migration; L474-489 "Daily Budget Planning" for limits and cadence). Do NOT re-create `guides/routines.md` — a standalone primer would duplicate 90%+ of recipes.md and invite drift (exactly the pattern vidux-improve cycles 1-7 were fixing). If a reader needs routines context, they read recipes.md. One source of truth.
- [DIRECTION] [2026-04-16] Recipes stay platform-agnostic in naming. `guides/recipes.md` may describe opinionated workflows but MUST NOT name specific tools (Greptile, Sentry, code-reviewer agent, Nia, Seer). Use generic phrasing: "If there are automation PR reviews (from review bots, code-review agents, or static-analysis comments), address them before merging." Specific tool wiring belongs in `/vidux-auto` (which is Leo's opinionated stack). This refines the 2026-04-14 "recipes may reference tools" direction — opinionated WORKFLOW yes, specific TOOL NAMES no. Leo: "try to not name tools explicitly like greptile but you say IF there are automation PR review please address before merging them in for example."
- [DIRECTION] [2026-04-16] PR Nurse local-CI check for resplit-ios = `tuist build` + all unit tests locally. The Nurse must not mark a draft PR ready-for-review until local unit tests pass. Resolves Q10. Leo: "local check for resplit ios tuist build unit tests locally all the unit tests would be ideal."
- [DIRECTION] [2026-04-16] T1-T4 Change Classification protects vidux core from churn. Most /insights findings are T1 (prompt) or T2 (CLAUDE.md). Recipes are T3 (companion). Core discipline (T4) only changes when the discipline itself is wrong. /insights report confirmed zero T4 changes across 10 sessions — the five principles are sound. Leo: "we need to have a framework for that... otherwise vidux is gonna keep changing."
- [DIRECTION] [2026-04-16] Codex automations adopt the same static-config pattern as Claude lanes: TOML `prompt` field becomes a thin shim → `~/.codex-automations/<name>/prompt.md`. Edit prompt.md freely without restarting the app. One-time TOML migration, then automations "never move." Leo: "automations point to a static file that we can easily change frequently without having to close codex app."
- [DIRECTION] [2026-04-16] vidux-auto should include a "Recommended CLAUDE.md Rules" section with battle-tested agent hygiene rules (re-read before edit, verify before completing, simple-creative-direct). These are the /insights-derived rules that any vidux user benefits from. Ship as open-source guidance alongside the skill. Leo: "mention CLAUDE.md best practices if you're gonna do this for open source, don't leave any tips behind."

## Open Questions
- Q1: Should contract tests track guide files (guides/*.md) or only SKILL.md? -> Action: decide after v3 guides land
- Q2: Draft-PR ownership — lane-owned (`gh pr create --draft` per automation). **Confirmed 2026-04-11.**
- Q3: Draft → Ready promotion — always human click. **Confirmed 2026-04-11.**
- Q4: Auto-merge — NEVER from automation. **Confirmed 2026-04-11.**
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
<!-- 5 tasks archived to ARCHIVE.md -->
