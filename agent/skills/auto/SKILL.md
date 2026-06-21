---
description: Use for safe local default-action, boundaries, proof, and durable receipts in Vidux.
---

# Auto

Default to safe local work when Vidux authority already decides the path.

Allowed:

- Read plans, ledger rows, git state, and local docs.
- Add scoped implementation plus evidence in a clean worktree.
- Run local proof commands that do not mutate external systems.

Stop for:

- Credentials, money, live external mutation, package publication, protected
  branch mutation, destructive cleanup, or messages to humans.

Every useful slice should leave a durable receipt: plan note, evidence file,
ledger row, branch, PR, or command output summary.
