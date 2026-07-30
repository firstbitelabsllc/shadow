# Vidux Automation Guide

Automation is optional. Vidux remains a repo-owned plan, proof, and resume
discipline; the selected coding host owns scheduling, model choice, worker
dispatch, and process lifecycle.

## When to automate

Automate only when all of these are true:

- the work repeats across multiple runs;
- the next action can be selected from durable repository state;
- the prompt can name an exact authority and bounded write scope;
- a failed or missed run is visible;
- the lane has a retirement condition.

Do the work directly when it is a one-off change, needs continuous human
judgment, or depends on conversation history that is not recorded in the repo.

## Durable state contract

Each run starts from the same public sources:

1. the owning `PLAN.md`;
2. repo-local evidence named by the plan;
3. the current revision and working-tree state;
4. open review or CI state, when relevant.

The scheduler's own logs are diagnostic only. Do not treat private runtime
telemetry as planning authority.
Public plans must not store account details, session identifiers, usage, cost,
credentials, or private machine paths.

## Keep lanes small

Prefer one writable owner for a plan and its connected code. Add a second lane
only when its surface is disjoint or read-only.

Useful roles:

- **Writer:** advances owned plan rows and verifies changes.
- **Reviewer:** reads a bounded diff and returns findings; it does not write.
- **Coordinator:** resolves ownership and ordering across several independent
  lanes; it does not become a second queue.

If two lanes can edit the same file, either split the files or serialize the
work.

## Subagent dispatch

Use the runtime's native subagent mechanism. Every child receives a working
directory, revision, allowed paths, acceptance checks, and output format. The
lead reviews and reproduces the important proof before updating the plan.

See `recipes/subagent-delegation.md` for research and implementation prompt
shapes.

## Lane bootstrap

### 1. Name the authority

Point the lane at one `PLAN.md`. Do not create a second task list in scheduler
metadata.

### 2. Define the boundary

State:

- mission and retirement condition;
- readable and writable paths;
- forbidden operations;
- task selection rule;
- verification required before completion;
- what to record for the next run.

### 3. Choose the least-powerful execution mode

Use a read-only or chat-scoped mode for research. Grant repository write access
only for implementation that needs it. Grant external publication, deployment,
or destructive authority separately and explicitly.

### 4. Register with the host

Use the host's supported automation surface and official documentation. Do not
write directly to undocumented databases or private runtime stores. Keep only a
stable pointer to the lane prompt in scheduler configuration.

### 5. Test one run

Confirm that the run:

- reads the intended plan and revision;
- respects the write boundary;
- makes no claim when no evidence was gathered;
- records a bounded proof or blocker;
- leaves a clear next action.

### 6. Retire cleanly

When the mission is complete, disable future runs through the host's supported
control. Preserve the repo-owned plan and proof required to understand what
shipped.

## Prompt structure

Use the eight blocks in [`harness.md`](harness.md#8-block-prompt-structure):
MISSION, SKILLS, GATE, AUTHORITY, CROSS-LANE, ROLE BOUNDARY, EXECUTION, and
CHECKPOINT.

Hard rules belong in EXECUTION: no force push, no hook bypass, no unrelated
paths, and no external side effect without explicit authority. CHECKPOINT names
the proof and next move, not runtime telemetry.

## See also

- `../SKILL.md` — core Vidux discipline
- `harness.md` — bounded prompt authoring
- `fleet-ops.md` — multi-lane ownership and handoff
- `recipes/codex-runtime.md` — safe Codex integration
