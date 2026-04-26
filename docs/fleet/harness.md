# Harness Authoring

This page is a docs-site summary of `guides/harness.md`, which is the repo's source guide for writing automation prompts.

## Core rule

The guide treats a prompt as a stateless harness:

- The harness stores process: mission, skills, guardrails, and role boundaries.
- `PLAN.md` stores state: tasks, decisions, evidence, and progress.
- Current task numbers, blockers, branch names, and other snapshots do not belong in the harness.

## The 8-block structure

`guides/harness.md` defines an eight-block order for prompt files:

1. `MISSION`
2. `SKILLS`
3. `GATE`
4. `AUTHORITY`
5. `CROSS-LANE`
6. `ROLE BOUNDARY`
7. `EXECUTION`
8. `CHECKPOINT`

The ordering is part of the contract. In the guide's words, rearranging or omitting blocks causes known failure modes.

## Roles

The authoring guide uses three lane roles:

- `Writer` ships code, executes plan tasks, and merges.
- `Radar` is read-only and produces evidence for a writer to promote.
- `Coordinator` watches fleet health and adjusts focus.

Each role uses a different gate shape. Writers read plan state and decide whether to ship. Radars scan reality instead of popping plan tasks. Coordinators look for collisions, idle loops, and other fleet-level problems.

## Prompt size guidance

The guide targets prompt files in the 2000-3000 character range:

- Under 1500 chars usually means a block is missing.
- 1500-3000 chars is the healthy range.
- Over 3000 chars should be audited for repeated doctrine.
- Over 4000 chars usually means the prompt is restating material that skills already provide.

## Common failure modes

The source guide calls out a few recurring mistakes:

- Gating on the wrong file and exiting before real work starts.
- Giving a scanner a writer-style gate.
- Restating doctrine that the agent already gets from the `vidux` skill.
- Using vague authority paths instead of explicit file locations.
- Omitting a role boundary or cross-lane read step.

## Where to go next

- Read [Fleet Operations](/fleet/operations) for the gate patterns and coordination rules that prompts rely on.
- Read [Prompt Template](/reference/prompt-template) for the docs-site reference version of the lane prompt structure.
- Read [Claude Code Lifecycle](/fleet/claude-lifecycle) or [Codex Automation Lifecycle](/fleet/codex-lifecycle) to see how the harness is consumed on each platform.
