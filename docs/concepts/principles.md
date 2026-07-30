# Five Principles

Five rules for deciding what to do next, what counts as proof, and how to leave
work resumable.

## Principle 1: Plan First, Code Second

`PLAN.md` is planning authority for the outcome, queue, decisions, constraints,
progress, proof references, and next move. When evidence changes the direction,
update the plan before extending the implementation.

Material plan claims should cite inspectable evidence: a repository path,
revision, test result, review finding, or linked artifact. Separate facts,
inferences, and unknowns.

```markdown
# Bad (no evidence)
- [pending] Task 1: Add rate limiting

# Good (evidence cited)
- [pending] T-1: Add rate limiting [Evidence: src/api/login.ts:42 — no throttle; focused regression missing]
```

## Principle 2: Design for Interruption

Sessions end and workers change. A cold reader should resume from `PLAN.md`,
the current Git revision and working tree, and the proof linked by the active
row. Preserve unexplained work before editing.

Vidux does not auto-recover sessions. It makes manual reconstruction bounded and
inspectable.

## Principle 3: Investigate Before Fixing

When root cause is unclear, map the relevant surfaces and competing hypotheses
before choosing a fix.

Use a linked investigation for a genuinely complex surface. Skip it for a small
repair with an obvious cause, owner, and gate.

```
Bug reported: "checkout double-charges on fast retry"

Wrong:
- Add idempotency check → ship → done

Right:
- Investigation: map all checkout code paths
- Root cause: no in-flight guard + no idempotency key
- Impact map: affects web and mobile checkout
- Fix spec: submit.ts:42 + retry.ts:18
- Tests: cover the retry race condition
- Gate: build + test + visual proof
```

## Principle 4: Self-Extend with a Brake

A maintainer or coding host may add newly discovered work when it belongs to
the stated outcome or closes a material risk. Vidux does not scan for or create
work automatically. Stop when the selected row's outcome exists and its gate
passes; record optional polish without reopening proven work.

## Principle 5: Prove It Mechanically

Never assert "it works" from source inspection alone. Run the smallest real gate
that proves the requested outcome. User-visible work normally needs direct
interaction or visual proof.

When an audit or grep produces a count or classification, spot-check at least one entry from each category before deciding on it. A grep hit is a lead, not a fact — a line matching "git push" might be a prohibition ("NEVER git push"), not an instruction.

```
Wrong: "The rate limiter is working — I can see it in the code."

Right:
- Build: passes
- Test: rate_limit_test.ts passes
- Manual: the first request beyond the declared limit returns 429
```

When a failure exposes a repeatable class, add a proportionate regression test,
constraint, or documented check.

## One-row default

The default cycle advances one bounded row through proof, records the result and
one cold-resume next move, then exits. The coding host may start another cycle;
Vidux itself does not drain queues, schedule work, or choose workers.

`vidux checkpoint` is an optional local convenience. If a local ledger is
configured it may append a row, but repository files and Git remain sufficient
authority. The row is neither proof by itself nor a publication gate.
