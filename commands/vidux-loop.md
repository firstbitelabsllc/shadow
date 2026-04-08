---
name: vidux-loop
description: Create and manage automation fleets — lean prompts, staggered schedules, writer/radar/coordinator roles, bimodal quality enforcement.
---

# /vidux-loop

Fleet builder for recurring automation loops. Creates Codex automations, Claude remote triggers, or standalone cron configs that run Vidux at scale.

## Subcommands

Parse the first argument to determine the mode:

- `/vidux-loop create <project> <role>` — generate a new automation
- `/vidux-loop fleet [project]` — show the slot map and fleet health
- `/vidux-loop validate [project]` — check prompt discipline and schedule collisions
- `/vidux-loop coordinator <project>` — generate the fleet coordinator automation
- No arguments — show this help.

---

## create

Generate an automation config and lean prompt for a project.

### Arguments

- `<project>` — project name (e.g., `acme`, `beacon`, `vidux`)
- `<role>` — one of: `writer`, `radar`, `coordinator`
- Optional: `<focus>` — narrow the radar or writer scope (e.g., `ux`, `revenue`, `flow`, `release-train`)

### Steps

1. **Discover existing fleet.** Scan for automation configs:
   - Codex: `~/.codex/automations/*/automation.toml` and any `automations/*/automation.toml` in nearby repos
   - Claude: remote triggers via `claude triggers list` if available
   - Local: any `automations/` directory in the current repo

2. **Build the slot map.** Parse all `rrule` or `BYMINUTE` fields. Map each automation to its minute-of-hour slots.

3. **Find the lowest-density slot.** Pick a 5-minute slot (:00, :05, :10, ..., :55) with the fewest existing automations. Writers get priority for isolated slots (they're heavier). Radars can share slots with other radars.

4. **Generate the schedule.**
   - Default cadence: every 30 minutes (BYMINUTE=X,X+30)
   - Coordinator cadence: every 2 hours (BYMINUTE=X, INTERVAL=2)
   - Never place more than 3 automations at the same minute offset

5. **Generate the lean prompt.** This is the core of Vidux fleet quality. The prompt MUST be under 15 lines. Vidux handles everything else.

#### Writer Prompt Template

```
Use [$vidux](<path-to-SKILL.md>) as writer for <project>.

Mission: <one-line mission from PLAN.md Purpose>

Authority store: <path to project PLAN.md>
Harness: <path to HARNESS.md, if exists>

Role: writer — ships code, merges, deploys. Only automation that touches <project> code.
Siblings: <comma-separated list of sibling automations for this project>

Design DNA:
- Keep working through the queue until a real boundary — context limit, genuine blocker, or external dependency.
- Full e2e per task: ideate → plan → dev → test → QA → commit. Not "smallest slice."
- <1-2 project-specific principles from PLAN.md Constraints>
```

#### Radar Prompt Template

```
Use [$vidux](<path-to-SKILL.md>) as radar for <project>.

Mission: <what this radar monitors — e.g., "Monitor UX quality and trust signals">

Authority store: <path to project PLAN.md>

Role: radar — read-only monitoring, evidence gathering, no code changes.
Siblings: <comma-separated list of sibling automations for this project>
Focus: <specific surface this radar monitors>

Design DNA:
- Check fast. If nothing changed since last run, checkpoint and exit in under 2 minutes.
- When something IS found, write thorough evidence — screenshots, logs, diffs, reproduction steps.
- <1-2 project-specific monitoring rules>
```

#### Coordinator Prompt Template

```
Use [$vidux](<path-to-SKILL.md>) as coordinator for <project> fleet.

Mission: Ensure the <project> automation fleet is making fire, not rubbing sticks.

Fleet manifest:
<list each automation: name, role, schedule, last memory entry date>

Coordination rules:
- Check each automation's memory.md for the last 3 entries.
- Bimodal quality check: runs should be < 2 min (quick check) or > 15 min (deep work). Flag 3-8 min runs as "stuck in the middle."
- If a writer has been "nothing to do" for 3+ cycles, suggest removing it or redirecting its focus.
- If a radar found issues but no writer picked them up, flag the handoff gap.
- Can adjust automation prompts to redirect focus. Cannot modify project code directly.
```

6. **Generate the automation config.** Based on the detected environment:

#### Codex automation.toml

```toml
version = 2

[schedule]
rrule = "FREQ=HOURLY;INTERVAL=1;BYMINUTE=<slot>,<slot+30>"

[task]
model = "gpt-5.4"
effort = "xhigh"
prompt = """
<generated prompt from above>
"""
execution_environment = "<local or cloud>"

[metadata]
project = "<project>"
role = "<writer|radar|coordinator>"
created_by = "vidux-loop"
created_at = "<ISO timestamp>"
```

#### Claude remote trigger

If on Claude Code and `claude triggers` is available:
```bash
claude triggers create \
  --name "<project>-<role>" \
  --schedule "*/30 * * * *" \
  --prompt "<generated prompt>"
```

If neither is available, output the prompt and schedule for manual setup.

7. **Update the fleet registry.** If a `fleet.json` exists in the project's vidux directory, append the new automation. If not, create one.

8. **Checkpoint.** Report what was created, the schedule slot, and the sibling list.

---

## fleet

Show the current automation fleet as a slot map.

### Steps

1. Discover all automations (same scan as `create` step 1).
2. Build and display the slot map:

```
Fleet: acme (5 automations)
  :00  acme-writer (writer, every 30m)
  :05  acme-ux-radar (radar, every 30m)
  :10  acme-flow-radar (radar, every 30m)
  :15  acme-android-writer (writer, every 30m)
  :20  acme-coordinator (coordinator, every 2h)

Load: max 2 concurrent at :30 (acme-writer + acme-ux-radar)
Gaps: :25, :35, :40, :45, :50, :55 — available for new automations
```

3. For each automation, show last memory entry date and bimodal quality:
```
Quality:
  acme-writer         last=2h ago  runs: 3 deep (22m avg), 1 quick (45s) ✓ bimodal
  acme-ux-radar       last=1h ago  runs: 4 quick (30s avg)               ✓ bimodal
  acme-flow-radar     last=30m ago runs: 2 mid (4m avg)                  ⚠ stuck-in-middle
```

---

## validate

Check fleet health and prompt discipline.

### Checks

1. **Schedule collisions** — more than 3 automations at the same minute offset.
2. **Prompt bloat** — any prompt over 20 lines (should be under 15).
3. **Doctrine restating** — prompts that restate vidux loop mechanics, checkpoint protocol, or enforcement rules. These belong in SKILL.md, not the prompt.
4. **Stale automations** — last memory entry older than 24 hours.
5. **Bimodal quality** — flag automations stuck in the 3-8 minute middle ground.
6. **Orphan radars** — radars with no corresponding writer to act on their findings.
7. **Missing coordinator** — project has 3+ automations but no coordinator.

### Output

```
Validation: acme fleet
  ✓ No schedule collisions
  ✓ All prompts under 15 lines
  ⚠ acme-flow-radar: prompt restates checkpoint protocol (remove lines 8-12)
  ✓ No stale automations
  ⚠ acme-flow-radar: 3 runs in 3-8 min range — investigate
  ✓ All radars have paired writers
  ✓ Coordinator present
```

---

## Bimodal Quality Model

Good automations are bimodal:

- **Quick check (< 2 min):** Read the plan, check the queue, nothing actionable, checkpoint and exit. This is healthy — it means the project is stable or waiting on external input.

- **Deep run (15+ min):** Pop a task, full e2e cycle — ideate, plan, code, test, QA, commit, checkpoint. The automation is doing real work. Multiple tasks may be completed in a single deep run.

- **Stuck in the middle (3-8 min):** The automation started something but didn't finish. Usually means the prompt is scoping too small ("smallest slice") or the plan tasks are too vague. Fix: make plan tasks concrete with clear gates, and make the prompt say "keep working through the queue."

The coordinator automation enforces this by checking run durations and flagging stuck-in-middle patterns.

---

## Hard Rules

- Generated prompts MUST be under 15 lines. Vidux SKILL.md handles the rest.
- Never restate vidux doctrine, loop mechanics, or checkpoint protocol in generated prompts.
- Never generate prompts that say "land the smallest verified slice" or "stop after one task."
- Writer prompts MUST say "keep working through the queue until a real boundary."
- Schedules MUST avoid thundering herd — max 3 automations per minute offset.
- Every fleet with 3+ automations MUST have a coordinator.
- Coordinator runs every 2 hours, not every 30 minutes.
