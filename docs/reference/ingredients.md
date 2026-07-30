# Vidux design ingredients

Vidux intentionally uses a small set of durable software-work patterns:

- **Repository-owned authority:** one `PLAN.md` records outcome, queue,
  constraints, decisions, progress, and resume state.
- **Bounded execution:** one active row becomes one reversible change and one
  named verification gate.
- **Mechanical proof:** a row is complete only when its requested outcome and
  named gate exist; activity or transport alone is not proof.
- **Cold resume:** a reader starts from the plan, current revision, working
  tree, and linked evidence instead of reconstructing chat.
- **Explicit ownership:** concurrent writers use disjoint surfaces and treat
  worker output as a draft until reviewed.
- **Optional projections:** the local browser and ledger can project plan
  state, but neither becomes a second authority.
- **Host boundary:** the coding host owns provider selection, dispatch,
  authentication, retries, scheduling, and process lifecycle.

## Deliberate exclusions

Vidux does not provide a workflow DSL, provider router, worker runtime, hosted
dashboard, shared-memory system, automatic worktree cleanup, or background
session manager. Those capabilities belong to the coding host or a separate
execution cockpit.
