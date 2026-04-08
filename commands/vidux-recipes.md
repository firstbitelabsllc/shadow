---
name: vidux-recipes
description: Automation fleet prescription. Lists known recipes, prescribes the right topology for a project, generates lean harnesses, and audits existing automations against doctrine.
---

# /vidux-recipes

Recipe book for vidux automation fleets. Knows the proven patterns, prescribes the right one for a given project, writes the harness, and audits what exists. Embodies the new automation doctrine: no mid-zone, taste, bounded recursion.

## Stage System

Uses the standard Vidux stage indicators for all output:
- `🔍 GATHER` — collecting evidence, reading PLAN.md, scanning automations
- `📐 PLAN` — synthesizing topology, picking the recipe, drafting the harness
- `⚡ EXECUTE` — writing the harness file, registering the automation
- `✅ VERIFY` — line count, doctrine alignment, prompt discipline checks
- `📌 CHECKPOINT` — recording the prescription, updating registries
- `🏁 COMPLETE` — recipe delivered, summary returned

## Subcommands

Parse the first argument to determine the mode:

- `/vidux-recipes list` — show all known automation recipes with when-to-use guidance
- `/vidux-recipes prescribe [project]` — analyze a project's PLAN.md and recommend the optimal fleet topology
- `/vidux-recipes write <role> <project>` — generate a lean harness for a specific role (writer/radar/coordinator/specialist)
- `/vidux-recipes audit [project]` — score existing automations against Doctrine 8 + new automation doctrine
- No arguments — show this help.

---

## list

Show all known automation recipes. READ-ONLY.

### Steps

1. **🔍 GATHER — Read this command's recipe catalog (below).** No external state to fetch.

2. **📐 PLAN — Format the catalog for the user.** Group by complexity. Always show: when to use, agent count, cron cadence, conflict risk, expected bimodal score.

3. **🏁 COMPLETE — Print the catalog.**

### Recipe Catalog

#### Recipe 1: Solo Writer

```
Solo Writer
───────────
When to use:    Single mission, single surface, ≤1 active plan, no UX nuance.
                Side projects, scripted maintenance, Stripe-style functional work.
Agent count:    1 (writer only)
Cron cadence:   Every 30 min, BYMINUTE=0,30
Conflict risk:  None — no siblings
Bimodal target: ≥90% (mostly deep, occasional quick)
Failure mode:   Writer drifts toward "always quick" because no radar surfaces work
```

#### Recipe 2: Writer + Radar

```
Writer + Radar  (THE DEFAULT — most common pattern)
──────────────
When to use:    Active project with 2-3 surfaces and recurring UX work.
                Radar finds work, writer ships it. Healthy handoff loop.
Agent count:    2 (1 writer + 1 radar)
Cron cadence:   Writer :00,:30 — Radar :05,:35
Conflict risk:  Low — staggered slots, radar is read-only
Bimodal target: Writer ≥85% deep, Radar ≥95% quick
Failure mode:   Handoff gap — radar finds issues, writer ignores. Add coordinator.
```

#### Recipe 3: Writer + 2 Radars + Coordinator (Acme Peak)

```
Writer + 2 Radars + Coordinator  (acme's peak topology)
─────────────────────────────────
When to use:    4+ active surfaces, known handoff problems, multi-domain monitoring
                (UX nuance + flow/perf/release health). Mature project entering polish.
Agent count:    4 (1 writer + ux-radar + flow/perf-radar + coordinator)
Cron cadence:   Writer :00,:30 — UX-radar :05,:35 — Flow-radar :10,:40 — Coord :15 (every 2h)
Conflict risk:  Medium — coordinator must enforce no thundering herd
Bimodal target: Fleet ≥85%, coordinator effectiveness ≥80%
Failure mode:   Coordinator blindness — fails to flag stuck-in-middle. Audit weekly.
```

#### Recipe 4: Multi-Repo Fleet

```
Multi-Repo Fleet  (e.g., acme-web + acme-ios + acme-currency-api)
────────────────
When to use:    Project spans multiple repos with distinct stacks (web/ios/api).
                Each repo gets its own specialized writer; one shared coordinator.
Agent count:    N writers (one per repo) + 1 cross-repo coordinator
                Optionally: 1 radar per repo for UX/perf
Cron cadence:   Stagger writers across :00, :15, :30, :45 to avoid concurrent builds
Conflict risk:  High — must avoid same-time builds, must share PLAN.md awareness
Bimodal target: Per-writer ≥85%, fleet-wide handoff gaps ≤2 cycles
Failure mode:   Writers diverge from shared mission. Coordinator must read all repos.
```

#### Recipe 5: Maintenance Mode

```
Maintenance Mode  (no automations)
────────────────
When to use:    Mature project in stable polish, no active push, low-feedback state.
                Beacon/Acme 2.0-style "1hr/week Wednesday" cycles.
                Or any project where automated work would generate noise.
Agent count:    0 — manual cycles only
Cron cadence:   None
Conflict risk:  None
Bimodal target: N/A (no automations to score)
Failure mode:   Project goes cold and forgotten. Calendar a manual review weekly.
```

#### Recipe 6: Deep Work Mode

```
Deep Work Mode  (single long persistent session, no cron)
──────────
When to use:    Active development sprint — Leo is heads-down for hours, doesn't want
                cron interruptions. Vidux runs as a single long-lived agent in one
                session, picking tasks continuously until human stops it.
Agent count:    1 persistent (no cron)
Cron cadence:   None — manual /vidux invocation kicks it off
Conflict risk:  None — single owner of the plan
Bimodal target: Always deep work (this is one giant deep run)
Failure mode:   Agent drifts off-mission without coordinator. Use for ≤4hr deep runs.
```

### Recipe Selection Heuristics (mirrors `prescribe`)

| Project state | Recipe |
|--------------|--------|
| 1 plan + 1 active surface | Solo Writer |
| 2-3 surfaces or recurring UX work | Writer + Radar |
| 4+ surfaces or handoff problems | Writer + 2 Radars + Coordinator |
| Multi-repo project | Multi-Repo Fleet |
| Quiet/maintenance | Maintenance Mode |
| Active dev sprint | Deep Work Mode |

---

## prescribe

Analyze a project's PLAN.md and prescribe the optimal fleet topology. READ-ONLY.

### Arguments

- `[project]` — project name (optional; defaults to the project in the current working directory if PLAN.md exists, else asks)

### Steps

1. **🔍 GATHER — Locate the project plan.**
   - Read `vidux.config.json` to resolve plan store mode.
   - Find `projects/<project>/PLAN.md` (external) or `PLAN.md` in current branch (inline).
   - If neither exists, fail with: "No PLAN.md found for `<project>`. Run /vidux-plan first."

2. **🔍 GATHER — Inventory existing automations for the project.**
   - Codex: `~/.codex/automations/<project>*/automation.toml`
   - Other: `~/.codex/automations/*<project>*/automation.toml`
   - Local: any `automations/` directory in the project repo
   - Record: count, roles (writer/radar/coordinator), schedules, last memory entry

3. **🔍 GATHER — Parse PLAN.md surface signals.**
   - Count `## Tasks` entries currently `[pending]` or `[in_progress]`
   - Count distinct surface keywords across tasks (UI, API, build, db, payments, etc.)
   - Detect compound tasks (`[Investigation: ...]`) — high-touch UX surfaces
   - Detect `## Active Worktrees` — concurrent shipper lanes
   - Detect mission-honesty markers (release boundary vs overall mission)
   - Detect repo references in Evidence section (single-repo vs multi-repo)

4. **📐 PLAN — Score against heuristics.**

   ```
   surfaces  = distinct surface count from tasks
   repos     = distinct repo paths cited in Evidence
   compound  = number of [Investigation:] tasks
   active    = number of [in_progress] or [pending] high-priority tasks
   handoff   = is there evidence of "radar found X but writer missed it"?
   stage     = active dev / polish / maintenance / cold
   ```

   Decision tree:
   ```
   IF stage == cold OR maintenance:                          → Recipe 5 (Maintenance Mode)
   ELIF Leo says "deep work" or active sprint signal:        → Recipe 6 (Deep Work Mode)
   ELIF repos > 1:                                            → Recipe 4 (Multi-Repo Fleet)
   ELIF surfaces ≥ 4 OR handoff == true OR compound ≥ 2:     → Recipe 3 (Writer + 2 Radars + Coord)
   ELIF surfaces ≥ 2 OR active ≥ 3:                          → Recipe 2 (Writer + Radar)
   ELSE:                                                      → Recipe 1 (Solo Writer)
   ```

5. **📐 PLAN — Compare to existing fleet.**
   - If existing fleet matches the prescribed recipe → "Fleet matches prescription. No changes needed."
   - If existing fleet is heavier than prescribed → "Fleet over-provisioned. Consider removing: <list>."
   - If existing fleet is lighter than prescribed → "Fleet under-provisioned. Consider adding: <list>."

6. **📌 CHECKPOINT — Generate the prescription report.**

   ```
   Prescription: <project>
   ────────────────────────────────────
   Plan signals:
     Active tasks:     7 ([in_progress]: 1, [pending]: 6)
     Distinct surfaces: 4 (Live Split, receipt-detail, screenshots, AP539)
     Compound tasks:   2 ([Investigation:] markers)
     Active worktrees: 1
     Repos:            1 (acme-ios)
     Stage:            polish (release boundary blocked, mission gaps live)

   Prescribed recipe: Recipe 3 — Writer + 2 Radars + Coordinator
     Why: 4 surfaces + 2 compound tasks + handoff debt in Progress entries.

   Existing fleet (acme):
     acme-vidux         writer       :00,:30
     acme-ios-ux-lab    radar/ux     :05,:35
     acme-launch-loop   radar/flow   :10,:40
     acme-oversight     coordinator  :15 (every 2h)

   Status: ✓ Fleet matches prescription. No changes needed.

   Watch for:
     - acme-launch-loop has 2 mid-zone runs in last 24h — audit prompt discipline
     - Coordinator missed 1 handoff gap (cycle 5 → cycle 7) — review oversight rules
   ```

7. **🏁 COMPLETE — Return the prescription.** Do not modify any files. The user decides what to act on.

---

## write

Generate a lean harness file for a specific role on a project. WRITES one new automation file.

### Arguments

- `<role>` — one of: `writer`, `radar`, `coordinator`, `specialist`
- `<project>` — project name
- Optional: `--focus <area>` — narrow the radar/specialist scope (e.g., `ux`, `revenue`, `release`)
- Optional: `--out <path>` — override the output path (default: `~/.codex/automations/<project>-<role>/automation.toml`)

### Steps

1. **🔍 GATHER — Read project context.**
   - Resolve PLAN.md path (same as `prescribe` step 1)
   - Read PLAN.md `## Purpose` (the mission)
   - Read PLAN.md `## Constraints` (project-specific rules)
   - Read sibling automations to build the siblings list
   - Find the lowest-density 5-minute slot on the cron grid

2. **📐 PLAN — Pick the template and gate based on role.**

   The harness MUST obey Doctrine 8 (≤15 lines) AND embody the new doctrine:
   - **No mid-zone:** explicit "keep working through the queue" directive
   - **Taste/self-extend:** "add tasks you discover; UI proof gates required"
   - **Bounded recursion:** "stop polishing surfaces that are honestly good enough"

   **Gate selection:** Writers and coordinators get the Quick check gate (checks PLAN.md task state). Radars and specialists with scanner focus get the SCAN gate (checks codebase for changes since last scan). See `guides/vidux/best-practices.md` Section 12 for both gate blocks.

3. **⚡ EXECUTE — Generate the harness.**

#### Writer Harness Template (≤15 lines)

```
Use [$vidux](<path-to-SKILL.md>) as writer for <project>.

Mission: <one-line from PLAN.md ## Purpose>

Authority store: <path to project PLAN.md>

Role: writer — ships code, merges, deploys. Only automation that touches <project> code.
Siblings: <comma-separated sibling automations>

Design DNA:
- Keep working through the queue until a real boundary (context limit, external block). Sub-5-min checkpoints with pending work = stopped too early.
- Self-extend the plan: when you fix a bug, file the related bugs you saw on the same surface. When you ship a feature, queue the polish/edge cases you spotted.
- UI work is not done until you have visual proof (simulator screenshot, $picasso, $bigapple, $playwright). The build passing is necessary but not sufficient.
- Bounded recursion: stop polishing surfaces that are honestly good enough. Move to the next mission gap, not the next pixel.
```

#### Radar Harness Template (≤15 lines, uses SCAN gate)

```
Use [$vidux](<path-to-SKILL.md>) as radar for <project>.

SCAN gate (run FIRST, before any other work):
1. Read last 3 memory notes. If same verdict 3× with no code changes → exit with "[SCAN] unchanged".
2. git log --since="<last scan>" -- <watched paths>. No changes + clean → exit.
3. Otherwise → full scan below.

Mission: Monitor <focus> for <project> — find work, never fix it.

Authority store: <path to project PLAN.md>
Role: radar — read-only. Never edits code.
Focus: <specific surface — UX, perf, flow, release-train, etc.>
Watched paths: <glob patterns for directories this radar monitors>

Design DNA:
- When found, write evidence with screenshots/repro/affected files. Hand off through PLAN.md ## Tasks.
- Surface BUNDLES — 3 tickets on the same area = one investigation, not three tasks.
- Stop adding polish to surfaces the writer already shipped this week. Hunt new surfaces, not pixels.
```

#### Coordinator Harness Template (≤15 lines)

```
Use [$vidux](<path-to-SKILL.md>) as coordinator for <project> fleet.

Mission: Keep the <project> fleet making fire, not rubbing sticks.

Fleet manifest (read live from disk each cycle):
<auto-generated list of sibling automations>

Coordination rules:
- Read each sibling's memory.md last 3 entries. Score bimodal: quick (<2m) or deep (15+m) is healthy; mid (3-8m) is stuck.
- If a writer is "nothing to do" 3+ cycles AND a radar has unactioned findings → flag the handoff gap and rewrite the writer's focus line.
- If a surface has 5+ recent commits and no new user-visible improvement → flag bounded-recursion violation, suggest moving to next mission gap.
- Adjust prompts. Never edit project code. Run every 2 hours, not every 30 minutes.
```

#### Specialist Harness Template (≤15 lines)

A specialist is a writer with a narrow surface (e.g., `acme-currency-api` writer that only touches the FX worker repo).

```
Use [$vidux](<path-to-SKILL.md>) as writer for <project>/<focus>.

Mission: <focus-specific mission, e.g., "Ship acme-currency-api FX pipeline">

Authority store: <path to project PLAN.md>
Repo scope: <single repo path — this writer only touches this repo>

Role: specialist writer — ships code in <repo> only. Other repos are out of scope.
Siblings: <comma-separated sibling automations>

Design DNA:
- Keep working through the queue for THIS repo until real boundary. Sub-5-min exit with pending work = stopped too early.
- Self-extend: file related bugs and polish on this surface as you find them. Hand off cross-repo work to the main writer via PLAN.md.
- UI/API proof gate: visual screenshot for UI; curl/test response for API. Build passing is not enough.
- Bounded recursion: do not optimize this repo past honest-good-enough while other repos have live mission gaps.
```

4. **✅ VERIFY — Doctrine and discipline checks.**
   - Line count ≤ 15 (Doctrine 8 hard limit). If over, fail and report which lines to cut.
   - Contains "keep working" or equivalent (no mid-zone)
   - Contains a UI/proof gate directive (taste)
   - Contains a "stop polishing" or "bounded recursion" line
   - Does NOT restate vidux loop mechanics, checkpoint protocol, or FSM rules
   - Does NOT contain "smallest slice" or "land one task" language
   - Schedule slot does not collide with > 2 existing automations

5. **⚡ EXECUTE — Write the automation.toml file.**

   ```toml
   version = 2

   [schedule]
   rrule = "FREQ=HOURLY;INTERVAL=1;BYMINUTE=<slot>,<slot+30>"

   [task]
   model = "o3"
   effort = "xhigh"
   prompt = """
   <generated harness from above>
   """
   execution_environment = "local"

   [metadata]
   project = "<project>"
   role = "<role>"
   recipe = "<recipe-name>"
   created_by = "vidux-recipes"
   created_at = "<ISO timestamp>"
   ```

   Default output path: `~/.codex/automations/<project>-<role>/automation.toml`

6. **📌 CHECKPOINT — Report what was created.**

   ```
   Created: <project>-<role>
   Path:    ~/.codex/automations/<project>-<role>/automation.toml
   Slot:    :<slot>, :<slot+30>
   Lines:   12/15
   Doctrine: ✓ keep-working ✓ proof-gate ✓ bounded-recursion ✓ no-restating
   Siblings: <list>
   ```

---

## audit

Score existing automations for a project against Doctrine 8 + the new automation doctrine. READ-ONLY.

### Arguments

- `[project]` — project name (optional; defaults to all projects)

### Steps

1. **🔍 GATHER — Discover automations.**
   - Codex: `~/.codex/automations/<project>*/automation.toml`
   - Local: `automations/<project>*/automation.toml` in nearby repos
   - For each: extract the prompt body (between `prompt = """` and `"""`)

2. **🔍 GATHER — Read recent memory.**
   - For each automation, read last 5 entries in `memory.md` (Codex) or equivalent
   - Extract run durations to compute bimodal distribution

3. **📐 PLAN — Score each prompt against the rubric.**

   | Check | Pass criteria | Severity if fail |
   |-------|--------------|------------------|
   | Line count | ≤ 15 lines (hard) / ≤ 20 lines (critical) | high / blocker |
   | Correct gate | Writers have Quick check gate; radars have SCAN gate (not Quick check) | high |
   | "Keep working" directive (writers only) | Contains "keep working" or "until a real boundary" | high |
   | UI proof gate (writers + UX radars) | Mentions screenshot/visual/$picasso/$bigapple/$playwright | medium |
   | Self-extend directive | Mentions "add tasks", "file related", "extend the plan" | medium |
   | Bounded recursion | Contains "good enough", "stop polishing", or "next mission gap" | medium |
   | No doctrine restating | Does NOT restate FSM, checkpoint protocol, loop mechanics | high |
   | No "smallest slice" anti-pattern | Does NOT contain "smallest slice", "land one task" | high |
   | Bimodal health | Last 5 runs ≥80% in quick or deep buckets | medium |

4. **📐 PLAN — Compute the audit score.**
   - Each pass = +1, each fail = 0
   - Out of 9 total checks
   - Flag any automation scoring ≤ 5 as needing rewrite
   - Flag any automation scoring 0 on a `high` severity check as critical

5. **📌 CHECKPOINT — Generate the audit report.**

   ```
   Audit: acme (4 automations)
   ────────────────────────────────────
   acme-vidux (writer)              8/9 ✓
     ✓ Lines 12/15
     ✓ correct gate (Quick check — writer)
     ✓ keep-working
     ✓ UI proof gate ($picasso, $bigapple)
     ✓ self-extend
     ✗ bounded-recursion — missing "good enough" line
     ✓ no doctrine restating
     ✓ no smallest-slice
     ✓ bimodal 4 deep / 1 quick

   acme-ios-ux-lab (radar/ux)       7/9 ⚠
     ✓ Lines 13/15
     ✓ correct gate (SCAN — radar)
     N/A keep-working (radar)
     ✓ UI proof gate
     ✓ self-extend (bundles)
     ✗ bounded-recursion — keeps polishing receipt-detail
     ✓ no doctrine restating
     ✓ no smallest-slice
     ⚠ bimodal 2 quick / 2 mid (3-5m) — mid-zone risk

   acme-launch-loop (radar/flow)    4/9 ✗ NEEDS REWRITE
     ✗ Lines 22/15 — over by 7
     ✗ correct gate — has Quick check gate, should be SCAN (radar)
     ✗ bounded-recursion missing
     ✗ doctrine restated lines 12-18 (FSM rules) — REMOVE
     ⚠ bimodal 1 quick / 3 mid — STUCK IN MIDDLE

   acme-oversight (coordinator)     8/9 ✓
     ✓ Lines 14/15
     ✓ correct gate (Quick check — coordinator)
     ✓ keep-working (coord variant)
     N/A UI proof gate (coordinator)
     ✓ bounded-recursion
     ✗ no handoff-gap detection rule
     ✓ no doctrine restating
     ✓ no smallest-slice
     ✓ bimodal 5 quick (healthy)

   ────────────────────────────────────
   Fleet score: 27/36 (75%)
   Critical: acme-launch-loop — wrong gate + rewrite via /vidux-recipes write radar acme --focus flow
   Watch:    acme-ios-ux-lab mid-zone trend
   ```

6. **🏁 COMPLETE — Print the report.** Do not auto-rewrite. The user runs `/vidux-recipes write` to fix specific automations.

---

## Hard Rules

- **Recipes are deterministic.** `list` always shows the same six recipes. Do not invent new recipes on the fly. New recipes get added to this command file via PR, not at runtime.
- **`prescribe` and `audit` are READ-ONLY.** They never modify automation files, PLAN.md, or any project state.
- **`write` outputs ONE file.** Never bulk-create multiple automations in one invocation. The user runs `write` per role.
- **Generated harnesses MUST be ≤ 15 lines.** Doctrine 8 is non-negotiable. If a template would exceed 15 lines, cut from the bottom (drop a Design DNA bullet) before adding length.
- **Generated harnesses MUST embody the new doctrine.** Every writer gets keep-working + proof-gate + bounded-recursion. Every radar gets bimodal + bundle + bounded-recursion. No exceptions.
- **Generated harnesses MUST NOT restate vidux mechanics.** No FSM rules, no checkpoint protocol, no loop step descriptions. SKILL.md owns those.
- **Always show your stage.** Every output block is prefixed with the stage indicator.
- **The command file itself can be longer than 15 lines.** Commands are skills, not harnesses. The 15-line limit applies only to the prompts that `write` generates.
