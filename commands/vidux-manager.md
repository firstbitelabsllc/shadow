---
name: vidux-manager
description: AI-powered self-diagnostic and testing agent. Conducts meta-research on vidux, runs plan quality tests, validates fleet health.
---

# /vidux-manager

Self-diagnostic agent for Vidux. Diagnoses runtime health, tests plan quality, investigates the system itself, and monitors fleet bimodal distribution.

## Stage System

Uses the standard Vidux stage indicators for all output:
- `🔍 GATHER` — collecting evidence, reading state, running scripts
- `📐 PLAN` — synthesizing findings, scoring quality, preparing reports
- `⚡ EXECUTE` — running tests, creating projects, executing scripts
- `✅ VERIFY` — validating results against baselines
- `📌 CHECKPOINT` — persisting findings, updating reports
- `🏁 COMPLETE` — diagnostic cycle done, report delivered

## Subcommands

Parse the first argument to determine the mode:

- `/vidux-manager diagnose [project]` — full diagnostic: doctor output + bimodal quality + prompt discipline audit
- `/vidux-manager test <project-type>` — create a fresh test project, run vidux, measure plan quality
- `/vidux-manager investigate <surface>` — meta-research on vidux itself
- `/vidux-manager fleet-health [project]` — bimodal distribution monitoring and fleet effectiveness
- No arguments — show this help.

---

## diagnose

Full AI-powered diagnostic of a project's vidux health. READ-ONLY — never modifies project code.

### Arguments

- `[project]` — project name (optional; defaults to all projects in `vidux.config.json`)

### Steps

1. **🔍 GATHER — Run vidux-doctor.sh.**
   ```bash
   bash scripts/vidux-doctor.sh --json --repo <project-path>
   ```
   Capture the full JSON output. Parse pass/warn/block counts and individual check results.

2. **🔍 GATHER — Parse bimodal quality from ledger.**
   ```bash
   source scripts/lib/ledger-query.sh
   ledger_fleet_health "<repo>" 24
   ```
   The ledger query layer reads real automation data from `~/.agent-ledger/activity.jsonl`.
   Classify each automation's recent runs into the bimodal buckets:
   - **Quick (< 2 min):** Healthy — nothing actionable, checkpoint and exit.
   - **Deep (15+ min):** Healthy — real work, full e2e cycle.
   - **Mid (3-8 min):** Stuck in the middle — investigate.
   Show the distribution as a histogram. Flag any automation with 3+ mid-zone runs.
   
   Also run handoff gap detection:
   ```bash
   ledger_handoff_gaps "<repo>" 4
   ```

3. **📐 PLAN — Audit prompt discipline.**
   Scan all automation prompts for the project (Codex `automation.toml`, Claude triggers, local `automations/`):
   - **Line count:** Flag prompts over 15 lines (hard limit) or over 20 lines (critical).
   - **Doctrine restatement %:** Search for restated vidux mechanics (checkpoint protocol, loop rules, enforcement language). Each restated concept is a violation. Calculate: `violations / total_prompt_lines * 100`.
   - **"Smallest slice" anti-pattern:** Flag any prompt containing "smallest slice," "land one task," or equivalent scope-limiting language.
   - **Missing "keep working" directive:** Flag writer prompts missing "keep working through the queue" or equivalent.

4. **📐 PLAN — Analyze automation memory.**
   Read the last 5 `memory.md` entries for each automation in the project:
   - Count "nothing to do" cycles. Flag if 3+ consecutive.
   - Detect handoff gaps: radar found issues but no writer picked them up within 2 cycles.
   - Detect stale automations: last entry older than 24 hours.
   - Detect coordinator blindness: coordinator exists but missed a stuck-in-middle pattern.

5. **📐 PLAN — Self-extension quality metric (Doctrine 12).**
   Count tasks in PLAN.md that were added by automations (look for `[Added-by: <automation-name>]`
   tags or tasks added in Progress entries after the initial plan creation).
   Compare against completed task count to compute the self-extension ratio:
   ```
   ratio = tasks_added_by_automations / tasks_completed_by_automations
   ```
   - **Healthy:** ratio ≤ 1.5 — automation adds proportionate work
   - **Warning:** ratio 1.5–3.0 — automation adds more than it ships
   - **Recursive overload:** ratio > 3.0 — Doctrine 12 violation, flag immediately
   
   If no `[Added-by:]` tags exist, fall back to counting tasks added in Progress entries
   that mention "added task" or "self-extended" vs entries that mention "completed" or "done."

6. **📌 CHECKPOINT — Generate diagnostic report.**

   ```
   Vidux Diagnostic Report: <project>
   ────────────────────────────────────
   Ledger:     ✓ 3205 entries (4.9M)
   Doctor:     12/14 pass, 2 warn, 0 block
   Bimodal:    74% (8 quick, 5 deep, 1 mid ⚠) target: >85%
   Handoffs:   1 gap (ux-radar → writer, 3 cycles)
   Prompts:    4/5 clean, 1 over 15 lines
   Doctrine:   3% restatement (target: 0%)
   Memory:     2 handoff gaps, 0 stale
   Self-ext:   ratio 1.2 (6 added / 5 completed) ✓
   ────────────────────────────────────
   Remediation:
     1. acme-flow-radar: 3 mid-zone runs — task granularity issue, review PLAN.md tasks
     2. acme-writer: prompt line 14 restates checkpoint protocol — remove
     3. Handoff gap: ux-radar flagged trust-badge issue cycle 12, writer missed until cycle 15
   ```

   Include specific, actionable remediation for every warning. Do not generate vague suggestions.

---

## test

Create a fresh isolated test project, run vidux, and measure plan quality against the 17-19/20 baseline.

### Arguments

- `<project-type>` — one of: `nextjs`, `ios`, `react-native`, `python`
- Optional: `--baseline <score>` — override the default 17/20 baseline

### Steps

1. **⚡ EXECUTE — Create isolated test directory.**
   ```bash
   mkdir -p tests/e2e/<type>-<timestamp>/
   ```
   Where `<timestamp>` is `YYYYMMDD-HHMMSS`. This directory is disposable. Never write test artifacts outside of `tests/e2e/`.

2. **⚡ EXECUTE — Seed minimal project scaffold.**
   Generate a minimal but realistic project for the type:
   - `nextjs`: `package.json`, `next.config.js`, `app/page.tsx`, `app/layout.tsx`
   - `ios`: `Package.swift`, `Sources/App.swift`, `Tests/AppTests.swift`
   - `react-native`: `package.json`, `app.json`, `App.tsx`, `metro.config.js`
   - `python`: `pyproject.toml`, `src/main.py`, `tests/test_main.py`

   Seed a minimal `vidux.config.json` with `plan_store.mode: inline` pointing to the test directory.

3. **⚡ EXECUTE — Seed vidux prompt and run.**
   Create a one-paragraph mission description appropriate to the project type. Run vidux in the test directory to generate a PLAN.md. Capture all output.

4. **✅ VERIFY — Measure plan quality.**
   Score the generated PLAN.md on a 20-point rubric:

   | Criterion                        | Points | What to check                                                   |
   |----------------------------------|--------|-----------------------------------------------------------------|
   | Evidence citations               | 4      | Every task cites at least one source. No unsourced claims.      |
   | Task specificity                 | 4      | Tasks have concrete gates, not vague descriptions.              |
   | Investigation depth              | 3      | Compound tasks created for messy surfaces. Root cause attempted. |
   | Constraint coverage              | 3      | ALWAYS/NEVER rules present. Reviewer preferences captured.      |
   | Decision Log seeded              | 2      | At least one durable direction logged with rationale.           |
   | Open Questions actionable        | 2      | Each Q has an action, not just a question mark.                 |
   | Structure completeness           | 2      | All required sections present (Purpose through Progress).       |

   **Baseline:** 17-19/20 per vidux-self-investigation. Score below 17 is drift. Score below 15 is regression.

5. **📌 CHECKPOINT — Report results.**

   ```
   Test Report: nextjs-20260406-143022
   ────────────────────────────────────
   Score: 18/20 (baseline: 17-19)
   Status: PASS ✓

   Breakdown:
     Evidence citations:  4/4
     Task specificity:    3/4 — Task 5 lacks a concrete gate
     Investigation depth: 3/3
     Constraint coverage: 3/3
     Decision Log:        2/2
     Open Questions:      2/2
     Structure:           1/2 — missing Surprises section

   Drift: none detected
   ```

   If score < 17, flag as drift and identify which criteria regressed compared to baseline.

---

## investigate

Meta-research on vidux itself. READ-ONLY — produces findings, does not modify vidux code or docs.

### Arguments

- `<surface>` — one of:
  - `framework-drift` — Are vidux patterns diverging across projects?
  - `nested-plans` — Is the L1/L2/L3 nesting working? Are investigations resolving?
  - `automation-quality` — Fleet-wide bimodal health, prompt discipline trends
  - `prompt-evolution` — How have automation prompts changed over time? Git archaeology.
  - `checkpoint-protocol` — Are checkpoints durable? Can a fresh agent rehydrate cleanly?

### Steps (all surfaces follow this pattern)

1. **🔍 GATHER — Collect evidence.**
   For each surface, gather from specific sources:

   **framework-drift:**
   - Diff PLAN.md structures across all projects in `projects/`.
   - Compare task formats, evidence citation styles, Decision Log conventions.
   - Check for diverging constraint patterns.

   **nested-plans:**
   - Find all `investigations/*.md` files across projects.
   - Check resolution rate: how many have a completed Fix Spec?
   - Check nesting depth: any L3 plans? Are they justified?
   - Check orphans: investigations referenced by tasks but file missing.

   **automation-quality:**
   - Run `vidux-fleet-quality.sh --json` for all projects.
   - Aggregate bimodal distributions fleet-wide.
   - Trend analysis: is mid-zone increasing or decreasing?

   **prompt-evolution:**
   - Git log on automation prompt files. Track line count over time.
   - Identify prompts that grew past 15 lines and when.
   - Check for doctrine restatement creep.

   **checkpoint-protocol:**
   - Read the last 3 Progress entries for each project.
   - Simulate rehydration: does the Progress entry contain enough for a fresh agent to pick up?
   - Check for "context lost" or "unclear state" patterns in Progress.

2. **📐 PLAN — Synthesize findings.**
   Produce a structured investigation report:

   ```
   Investigation: <surface>
   Date: <ISO date>
   ────────────────────────────────────
   Finding 1: <title>
     Evidence: <specific files, lines, diffs>
     Severity: low | medium | high
     Recommendation: <actionable fix>

   Finding 2: ...

   Summary:
     Findings: N (H high, M medium, L low)
     Trend: improving | stable | degrading
   ```

3. **📌 CHECKPOINT — Persist findings.**
   Investigation findings are evidence for the vidux improvement cycle. Note them in the output but do NOT modify vidux files. The human or a writer automation decides what to act on.

---

## fleet-health

Bimodal distribution monitoring and fleet effectiveness report. READ-ONLY.

### Arguments

- `[project]` — project name (optional; defaults to all projects)

### Steps

1. **🔍 GATHER — Collect fleet data from ledger.**
   ```bash
   source scripts/lib/ledger-query.sh
   ledger_fleet_health "<repo>" 24    # full fleet health JSON
   ledger_automation_runs "<repo>" 24 # per-automation breakdown
   ledger_handoff_gaps "<repo>" 4     # radar→writer lag detection
   ```
   The ledger at `~/.agent-ledger/activity.jsonl` is the single source of truth for all
   automation activity across Claude Code, Cursor, and Codex. No separate fleet scripts needed.
   Also read the last 5 `memory.md` entries per automation for qualitative analysis.

2. **📐 PLAN — Assess bimodal distribution.**
   This is non-negotiable: every fleet report shows the quick/deep/stuck distribution.

   Classify each automation's runs:
   - **Quick (< 2 min):** Checkpoint-and-exit. Healthy for stable projects.
   - **Deep (15+ min):** Full e2e work. Healthy for active projects.
   - **Mid (3-8 min):** Stuck in the middle. Always a problem.

   Fleet-wide bimodal score:
   ```
   bimodal_score = (quick_runs + deep_runs) / total_runs * 100
   ```
   Target: > 85%. Below 70% is critical.

3. **📐 PLAN — Detect handoff gaps.**
   For each project with both radars and writers:
   - Check if radar findings appear in writer task queues within 2 cycles.
   - Flag gaps where radar evidence was ignored or delayed.
   - Check coordinator logs for whether it noticed the gap.

4. **📐 PLAN — Assess coordinator effectiveness.**
   For each project with a coordinator:
   - Did the coordinator flag stuck-in-middle patterns?
   - Did the coordinator redirect idle writers?
   - Did the coordinator notice handoff gaps?
   - Score: `actions_taken / issues_present * 100`. Target: > 80%.

5. **📌 CHECKPOINT — Generate fleet health report.**

   ```
   Fleet Health: <project>
   ────────────────────────────────────
   Automations: 5 (2 writers, 2 radars, 1 coordinator)
   Bimodal Score: 88% ✓ (target: >85%)

   Distribution (last 24h):
     Quick (<2m):   ████████████  12 runs (48%)
     Deep (15+m):   ██████████    10 runs (40%)
     Mid (3-8m):    ███            3 runs (12%) ⚠

   Per-Automation:
     acme-writer         deep=5, quick=2, mid=0    ✓
     acme-android-writer deep=3, quick=3, mid=2    ⚠ mid-zone
     acme-ux-radar       quick=6, deep=0, mid=0    ✓
     acme-flow-radar     quick=4, deep=0, mid=1    ⚠ mid-zone
     acme-coordinator    quick=2, deep=1, mid=0    ✓

   Handoff Gaps: 1
     ux-radar found trust-badge issue (cycle 12) → writer picked up (cycle 15)
     Gap: 3 cycles (target: ≤2)

   Coordinator Effectiveness: 75% (3/4 issues flagged)
     ✓ Flagged flow-radar mid-zone
     ✓ Redirected idle android-writer
     ✓ Noticed stale ux-radar entry
     ✗ Missed trust-badge handoff gap
   ```

---

## Hard Rules

- **Diagnostics are READ-ONLY.** The `diagnose`, `investigate`, and `fleet-health` modes NEVER modify project code, PLAN.md files, automation prompts, or any vidux files.
- **Tests are ISOLATED.** The `test` mode creates projects ONLY in `tests/e2e/<type>-<timestamp>/`. Never write test artifacts elsewhere.
- **Quality scoring references baseline.** The 17-19/20 baseline from vidux-self-investigation is the reference. Do not invent new baselines.
- **Bimodal assessment is non-negotiable.** Every fleet report and every diagnostic report includes the quick/deep/stuck distribution. No exceptions.
- **Investigation findings are evidence, not actions.** The `investigate` mode produces findings. It does not modify vidux. The improvement cycle decides what to act on.
- **Prompt discipline is strict.** Automation prompts over 15 lines are violations. Doctrine restatement is a violation. "Smallest slice" language is a violation.
- **Always show your stage.** Every output block is prefixed with the stage indicator. If output lacks a stage prefix, you are doing it wrong.
