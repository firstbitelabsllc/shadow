# What Shadow does

Shadow is one local product with two bounded jobs:

1. Brief you on the Outcome, current move, proof, and next A/B/C decision.
2. Hand one sealed, path-bounded task to native Codex, Claude Code, or Cursor
   only when you ask.

It reads repository-owned `PLAN.md`. It stores bounded receipts only inside
that Git project.
The attempt receipt (`shadow.host-attempt.v1`) contains generic host facts and
the frozen task's SHA-256 only. Shadow does not choose a model, relay
credentials, keep raw conversations, or run a background agent system.
