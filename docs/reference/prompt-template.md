# Bounded worker prompt

Use this template when a coding host runs a worker:

```text
Outcome:
  <one observable result>

Authority:
  Read <repo>/PLAN.md and the current revision before acting.

Scope:
  Read: <bounded paths>
  Write: <exact paths, or "none">

Gate:
  <command or inspection that proves the result>

Boundaries:
  Do not touch another worker's surface.
  Do not publish, spend money, send messages, or cross a security boundary
  unless the task explicitly authorizes it.

Return:
  Changed paths, proof, unresolved uncertainty, and one cold-resume next move.
```

Keep current task state in the plan, not in a reusable prompt. Treat a worker's
answer as a draft until the owner reviews the diff and reproduces important
claims.
