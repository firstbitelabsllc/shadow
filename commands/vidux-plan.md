---
name: vidux-plan
description: Plan-only mode. Creates or refines the authority PLAN without writing code.
---

# /vidux-plan

Plan-only mode. You will not write code in this mode.

## Startup

1. Load the `vidux` skill and `LOOP.md`.
2. Read `vidux.config.json`.
3. Resolve the authority plan location from config:
   - external mode: `projects/<name>/PLAN.md`
   - inline mode: `PLAN.md` in the current repo branch
4. Use any arguments as the mission description or refinement direction.

## If The Authority PLAN Does Not Exist: CREATE

### Phase 1: GATHER (fan out)

Research the problem space from multiple angles, in parallel where possible:

**Evidence gathering:**
- Search the codebase for relevant patterns, existing implementations, prior art.
- Look for related documentation, design docs, or specifications.
- Identify existing conventions and team patterns.

**Architecture analysis:**
- Map the dependency graph for affected areas.
- Identify integration points and boundaries.
- Note existing patterns that must be followed.

**Constraint discovery:**
- Find reviewer preferences from past PR comments and reviews.
- Identify build system requirements and CI constraints.
- Note any "always/never" rules from project conventions.

**Task decomposition:**
- Break the project into ordered, checkboxed tasks.
- Prefer FSM tags for new tasks: `[pending]`, `[in_progress]`, `[completed]`, `[blocked]`.
- Identify dependencies between tasks.
- Mark parallelizable tasks with `[P]`.
- Estimate relative complexity.

If a bug surface looks messy or clustered, do not create an atomic task. Create a compound task:

```markdown
- [pending] Task N: Fix <surface> [Investigation: `investigations/<slug>.md`] [Evidence: ...]
```

### Phase 2: SYNTHESIZE

Combine all research into a single `PLAN.md` with these required sections:

- **Purpose**: one paragraph, user-visible goal.
- **Evidence**: cited findings from research. Every entry has a source.
- **Decision Log**: durable directions that later runs must not undo.
- **Constraints**: ALWAYS / ASK FIRST / NEVER rules. Reviewer preferences.
- **Decisions**: what was decided, alternatives considered, rationale.
- **Tasks**: ordered, evidence-cited, with `[Depends:]` markers and FSM tags.
- **Open Questions**: unknowns that need research, each with an action.
- **Surprises**: (empty at creation, filled during execution).
- **Progress**: living log, updated each cycle.

Store long-form research in `evidence/YYYY-MM-DD-<slug>.md` when the findings are more than a few bullets.

For compound bug work, create the investigation file with this minimum shape:
- Reporter says
- Evidence
- Root Cause
- Impact Map
- Fix Spec
- Regression Tests
- Gate

### Phase 3: CRITIQUE

Review the plan for:
- Tasks without evidence citations (remove or research them).
- Missing dependencies between tasks.
- Assumptions that haven't been validated.
- Scope creep beyond the stated purpose.

## If The Authority PLAN Exists: REFINE

- Re-run the GATHER phase for any tasks lacking evidence.
- Research only the open questions that block the next task.
- Update the Evidence section with new findings.
- Re-order tasks if dependencies have changed.
- Add new tasks discovered during research.
- Split unstable bug surfaces into compound tasks with investigation files.
- Remove tasks that are no longer relevant.
- Update Constraints if new conventions or preferences were found.

## Output

Commit the new or updated PLAN.md. The commit message should describe what was planned or refined.

- If external mode, commit to the skills repo.
- If inline mode, commit to a feature branch (never main).

## Hard Rules

- NEVER write code. Not even example code. Not even test stubs.
- NEVER create files outside of the documentation tree, except authority-plan companion docs like `evidence/` and `investigations/`.
- Every plan entry MUST cite at least one evidence source.
- A plan entry without evidence is a guess. Remove it or research it.
