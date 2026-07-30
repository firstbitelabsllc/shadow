# Automation Prompt Authoring

Reference for writing bounded automation prompts, or harnesses.

---

## Core Rule (Doctrine 8)

An automation prompt is a **stateless harness**: it encodes the end goal and
project-specific instructions an agent cannot infer. It never contains current
state.

**The harness is the process.** The owning `PLAN.md` is the queue, decision,
proof-reference, and resume authority. Never mix current-state snapshots into
the harness.

**In the harness:** end goal, authority plan path, role boundary, project
constraints, verification, and retirement condition.

**Never in the harness:** task numbers, progress summaries, current branches,
current blockers, account data, session identifiers, usage, costs, credentials,
or private machine paths.

One loop per project/mission. If a loop exists, refine it -- do not create a sibling.

---

## 8-Block Prompt Structure

Every harness follows these eight blocks, in this order. Rearranging or omitting blocks produces known failure modes.

```
1. MISSION        -- One line. User-visible goal. No implementation details.
2. SKILLS         -- Load only public, mission-relevant guidance.
3. GATE           -- Read-only check that decides work or a cited exit.
4. AUTHORITY      -- Read order for plan files. Primary state file is #1.
5. CROSS-LANE     -- Read sibling memory + hot-files. Dedup, yield, skip.
6. ROLE BOUNDARY  -- What this lane owns. What belongs to siblings.
7. EXECUTION      -- One bounded row, its real gate, and an exit.
8. CHECKPOINT     -- Proof, remaining risk, and one resume action.
```

**Why this order:** the gate prevents unnecessary mutation. Cross-lane
coordination follows authority so the agent can detect ownership conflicts
before editing.

---

## Writer, Radar, and Coordinator Roles

Automations use one of three roles:

- **Writer** — advances owned plan rows and verifies changes.
- **Reviewer** — gathers evidence and returns findings; no code changes.
- **Coordinator** — resolves ownership and ordering across several lanes.

**Gate pattern (writers):**
1. Check the named revision and working-tree state.
2. Read the plan for actionable rows in this lane's scope.
3. If a task exists: execute one bounded row.
4. If no task exists: exit without inventing work.
5. Record proof, uncertainty, and one resume action.

**Gate pattern (reviewers):** use the SCAN gate in `guides/fleet-ops.md`.
Reviewers inspect the named scope and return cited findings or a cited clean
result. They do not claim implementation work.

---

## Size Guidance

Use the shortest prompt that preserves all eight blocks. Bloat usually hides in
repeated doctrine, copied current state, or explanations that do not change
behavior.

**The test:** Can you delete a sentence without changing the agent's behavior? If yes, delete it.

---

## Common Mistakes

1. **Wrong authority.** A meta-plan or copied task list can hide live work.
2. **Reviewer with a writer gate.** It checks the queue but never scans its
   review surface.
3. **Restated doctrine.** Repetition makes the prompt harder to audit.
4. **Vague authority.** Name a repo-relative plan and exact owned paths.
5. **Missing stop rule.** A blocked lane keeps rereading without new evidence.
6. **Missing role boundary.** Two lanes edit the same surface.
7. **Missing cross-lane check.** A lane duplicates work already in progress.
8. **Uncited empty exit.** A clean exit must name what was checked.

---

## Interactive request refinement

For an ambiguous interactive request, gather repository context and restate a
bounded execution brief before acting.

```
RAW INPUT -> GATHER -> BOUND -> EXECUTE -> VERIFY
```

**GATHER:** current revision, working-tree state, existing plan, relevant files,
and recent proof.

**BOUND:** choose the smallest fitting mode:

| Signal | Mode |
|---|---|
| automation, schedule, loop, recurring | **HARNESS** -- produce an evergreen prompt per Doctrine 8 |
| plan, project, investigate, research | **PLAN** -- produce mission description, no code |
| Everything else | **EXECUTE** -- produce specific, evidence-cited, actionable prompt |

**Rules:** use real context only. Never invent sources. If several unrelated
missions fit, narrow to the one owned by the named plan. A harness never embeds
current task numbers, branches, blockers, or runtime receipts.
