# The Vidux loop

Every run is resumable from repository files:

1. **Read** — open `PLAN.md`, the current revision, the working tree, and named
   proof.
2. **Assess** — resume the active row or take the highest unblocked row.
3. **Act** — make one bounded, reversible change.
4. **Verify** — run the repository's real gate and inspect the result.
5. **Checkpoint** — record what changed, what passed, and the next cold-resume
   move.

## Ownership

One worker owns a writable surface at a time. Parallel work is safe only when
surfaces are disjoint. Worker output remains a draft until the owning agent
reviews it and reproduces the important proof.

## Recovery

Before creating a branch or worktree, inspect existing branches, worktrees, and
uncommitted changes with Git's normal commands. Vidux ships no cleanup
automation and never removes another worker's checkout.

## Completion

A row is complete when its requested outcome exists, its named gate passes, and
the plan contains enough proof and next-state context for a cold reader. A
commit, chat message, or activity count alone is not proof.
