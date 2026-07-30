# Recipe: Subagent Delegation

Use a child agent for a bounded task while one lead keeps authority, reviews the
result, and owns the final proof. Vidux does not choose a model or dispatch a
worker; use the primitives supplied by your coding runtime.

## When to use

- A read-only investigation can run independently.
- An implementation has an exact file boundary and acceptance test.
- Parallel work will not make two agents edit the same file.
- The lead can reproduce the important claims before accepting the result.

Do the work directly when the task is tiny, inseparable from a design decision,
or cannot be isolated safely.

## Research delegation

The child reads the larger working set and returns a compact, cited result. A
useful response contract is:

```text
Summary: at most three sentences.
Evidence: at most three file:line references.
Recommendation: one next action.
```

Use this shape for audits, investigations, cross-file searches, and independent
review. A summary is a draft, not proof: the lead checks the cited evidence
before changing the plan.

## Implementation delegation

Every implementation prompt should state:

```text
Task: one sentence.
Files: exact paths the child may edit.
Spec: required behavior and edge cases.
Acceptance: commands or observations that must pass.
Out of scope: adjacent work the child must not change.
```

The child edits only the listed paths and reports the diff plus test output. The
lead reviews the working tree, runs the acceptance checks, and decides whether
to keep the change. The child does not commit, push, merge, publish, or mutate
repository metadata unless the owning plan explicitly grants that authority.

## Review checklist

Review in this order:

1. **Scope:** only allowed paths changed.
2. **Spec:** every edit maps to a requirement.
3. **Drift:** no unrelated refactor, formatting sweep, or dependency change.
4. **Correctness:** edge cases and failure behavior match the prompt.
5. **Fit:** naming and structure match the surrounding repository.
6. **Proof:** the lead reproduces the relevant checks.
7. **Handoff:** the owning `PLAN.md` records the accepted result and next move.

If a draft is unusable, leave the existing work intact, isolate or revert only
the child's bounded paths, and issue a narrower prompt. Never discard unrelated
working-tree changes.

## Parallelism rules

- One active owner per writable file.
- Prefer read-only fan-out; funnel writes through one lead.
- Give every child a working directory, revision, allowed paths, and output
  format.
- Treat missing or empty output as unknown, not success.
- Keep destructive changes, schema migrations, credentials, release settings,
  and external publication with the lead.

## What to record

Record decisions and accepted proof, not provider telemetry. A plan update may
name the delegated task, the reviewed evidence, and the next action. Do not
store account details, session identifiers, usage, cost, raw transcripts, or
private runtime logs in a public plan.

## See also

- `guides/automation.md` — durable lane boundaries
- `guides/recipes/codex-runtime.md` — applying the same contract in Codex
- `docs/doctrine/DOCTRINE.md` — plan, proof, and resume discipline
