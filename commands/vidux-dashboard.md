---
name: vidux-dashboard
description: Cross-project visibility dashboard. Shows all vidux plans as a tree with status, health, and codex fleet state from 3 discovery sources.
---

# /vidux-dashboard

Read-only, cross-project status tree. Discovers plans and automations from local, Codex, and external sources and renders a unified dashboard.

## Flags

- `--json` — output as JSON instead of the tree view
- `--dir PATH` — add an extra scan directory (can be repeated)
- `--codex-only` — show only the Codex fleet section
- `--depth N` — max nesting depth in the tree (default 3)

## Steps

1. **Read config.** Load `vidux.config.json` from the repo root.
   - Resolve `plan_store.path` for the local plan directory (default: `projects`).
   - Read `external_plan_roots` array if present (list of absolute paths to other repos or directories containing `PLAN.md` files).
   - If `--dir PATH` was given, append each path to the scan list.

2. **Discover plans from 3 sources.**

   ### Source 1 — Local (this repo)

   Scan `<plan_store.path>/*/PLAN.md` relative to the repo root.
   Each match is a project. The directory name is the project name.

   ### Source 2 — Codex fleet

   Scan for automation configs:
   - `~/.codex/automations/*/automation.toml`
   - `~/.codex/automations/*/PLAN.md`
   - Any `automations/*/automation.toml` in nearby repos discovered via `external_plan_roots`

   For each `automation.toml`, parse:
   - `[metadata].project` — the project this automation belongs to
   - `[metadata].role` — writer, radar, or coordinator
   - `[schedule].rrule` — the cron/rrule schedule
   - `[task].prompt` — for prompt-length checks

   For each automation directory, check for a `memory.md` file and read the timestamp of the last entry.

   ### Source 3 — External plan roots

   Scan each path in `external_plan_roots` for:
   - `PLAN.md` at the root
   - `projects/*/PLAN.md` (same structure as local)
   - `*/PLAN.md` one level deep

   Each discovered `PLAN.md` becomes a project node.

3. **Parse each plan.** For every discovered `PLAN.md`:

   - **Phase:** Read the Tasks section. Determine the current phase using the same logic as `/vidux-status`:
     - EXECUTE if a task is `[in_progress]`
     - GATHER if the next task lacks evidence
     - PLAN if the next task is blocked by open questions
     - VERIFY if all tasks are done but final verification is pending
     - COMPLETE if all tasks are complete and verified
   - **Current task:** The first `[in_progress]` task, or "idle" if none.
   - **Last progress timestamp:** The most recent entry in the Progress section. Parse the timestamp and compute relative age (e.g., "2h ago", "3d ago").
   - **Task counts:** Completed vs total tasks.

4. **Parse Codex automations.** For each automation:

   - **Status:** Derive from the last `memory.md` entry:
     - If last entry < 1 hour ago and contains work evidence: `active`
     - If last entry < 1 hour ago and says "nothing actionable": `idle`
     - If last entry > 24 hours ago: `stale`
     - Otherwise: `ok`
   - **Bimodal quality:** Check run durations from `memory.md` entries. Flag `stuck-in-middle` if the most recent 3 runs average 3-8 minutes.
   - **Last run:** Relative timestamp of the most recent `memory.md` entry.

5. **Build the tree.** Assemble nodes respecting `--depth N` (default 3):

   - **Level 0:** Source group header (this repo, external project, Codex fleet)
   - **Level 1:** Project or automation group
   - **Level 2:** Individual plans, tasks, or automation entries
   - **Level 3:** Sub-tasks or automation details (only if depth allows)

   If `--codex-only` is set, skip Source 1 and Source 3 entirely.

6. **Render output.**

   ### Tree view (default)

   ```
   VIDUX DASHBOARD — <today's date>

   📦 vidux (this repo)
     📐 PLAN.md — Phase 10 in progress — 2m ago
       🔍 self-investigation — COMPLETE — 6h ago
       🔍 context-ops — active — 1h ago

   📦 acme
     📐 PLAN.md — camera routing — 3h ago

   📦 beacon
     📐 PLAN.md — idle — 2d ago

   🤖 Codex Fleet (3 automations)
     ✅ acme-writer — last run 30m ago
     ✅ acme-ux-radar — last run 1h ago — idle
     ⚠️ beacon-ux-radar — stuck-in-middle — 20m ago
   ```

   **Stage emojis:**
   - 📦 — project group
   - 📐 — plan file
   - 🔍 — sub-plan or investigation
   - 🤖 — Codex fleet group
   - ✅ — healthy automation (active or idle, bimodal OK)
   - ⚠️ — automation needs attention (stale, stuck-in-middle, or errored)
   - 🏁 — completed plan or phase

   ### JSON view (`--json`)

   Output a JSON object:

   ```json
   {
     "generated_at": "2026-04-06T14:30:00Z",
     "sources": {
       "local": {
         "root": "projects",
         "projects": [
           {
             "name": "vidux",
             "plan_path": "projects/vidux/PLAN.md",
             "phase": "EXECUTE",
             "current_task": "context-ops",
             "tasks_complete": 7,
             "tasks_total": 15,
             "last_progress": "2026-04-06T14:28:00Z",
             "last_progress_relative": "2m ago",
             "sub_plans": [
               {
                 "name": "self-investigation",
                 "status": "COMPLETE",
                 "last_progress_relative": "6h ago"
               }
             ]
           }
         ]
       },
       "external": {
         "projects": []
       },
       "codex": {
         "automation_count": 3,
         "automations": [
           {
             "name": "acme-writer",
             "project": "acme",
             "role": "writer",
             "status": "active",
             "bimodal": "ok",
             "last_run": "2026-04-06T14:00:00Z",
             "last_run_relative": "30m ago",
             "schedule": "FREQ=HOURLY;INTERVAL=1;BYMINUTE=0,30"
           }
         ]
       }
     }
   }
   ```

## Edge Cases

- **No plans found anywhere.** Report:
  ```
  VIDUX DASHBOARD — <date>

  No plans discovered. Run /vidux to start a plan, or add external_plan_roots to vidux.config.json.
  ```

- **Config missing `external_plan_roots`.** Skip Source 3 silently. Do not warn — this is the expected default state.

- **Codex directory does not exist.** Skip Source 2 silently. Show the Codex Fleet section as:
  ```
  🤖 Codex Fleet (no automations found)
  ```

- **`--dir PATH` points to a nonexistent directory.** Warn inline:
  ```
  ⚠️ --dir /path/to/missing — directory not found, skipping
  ```

- **PLAN.md exists but is empty or unparseable.** Show the project with status "unreadable":
  ```
  📦 myproject
    📐 PLAN.md — unreadable — check file format
  ```

## Hard Rules

- Read only. Do not modify any files.
- Keep tree output under 50 lines. If more projects/automations exist, collapse with a count: `... and 4 more projects`.
- Relative timestamps only in tree view. ISO timestamps in JSON view (with a `_relative` companion field).
- Do not show task-level detail in the tree unless `--depth` is 3 or greater.
- If `--json` is set, output valid JSON only — no prose, no markdown.
- Codex fleet section always appears last in the tree.
