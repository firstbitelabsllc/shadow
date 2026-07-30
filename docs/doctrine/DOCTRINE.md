# Vidux Doctrine

> A compact contract for durable plan, proof, and resume state.

## Working Philosophy

Read current repository state before acting. Make one bounded change, verify it,
and leave the next move clear.

## 1. Plan is authority

`PLAN.md` owns work, decisions, constraints, progress, and the references needed
to verify a completed row. If code and plan disagree, reconcile the plan before
extending the implementation.

## 2. Unidirectional flow

READ -> ASSESS -> ACT -> VERIFY -> CHECKPOINT -> READ. Never skip a step. To change code the plan does not specify, update the plan first.

## 3. Front-load intent

Name the outcome, constraint, and acceptance check before editing. The useful
ratio of planning to implementation varies by task; the invariant is that code
must have a stated purpose and proof.

## 4. Evidence over instinct

Separate facts, inferences, and unknowns. Cite repository paths, revisions,
tests, logs, or review findings close to the claim they support. A worker's
summary is not proof until the lead checks its evidence.

## 5. Design for completion

Runs end and context can disappear. Durable state belongs in repo-owned files,
not chat history or private runtime logs. A checkpoint states outcome, proof,
remaining risk, and one resume action.

## 6. Process fixes > code fixes

When a failure exposes a repeatable class, add a proportionate regression test,
constraint, or documented check. Do not add process for a one-off event unless
it prevents a plausible recurrence.

## 7. Bug tickets are nested investigations

When several symptoms share a surface or repeated fixes fail, open one
`[Investigation: investigations/<slug>.md]`. Record competing hypotheses and
the evidence that distinguishes them before choosing another fix.

## 8. Automation prompts are harnesses, not snapshots

An automation prompt encodes mission, authority, selection rule, verification,
and retirement. `PLAN.md` holds current state. Do not copy current task numbers,
branches, blockers, account data, or session details into the harness.

## 9. Subagent coordinator pattern

Fan out independent read-only work and fan it back through one lead. Writable
lanes need disjoint file ownership. Never let several agents edit the same file
or treat an unreviewed child result as accepted.

---

## Loop Discipline (Principles 10-12)

These principles keep a run from stopping at setup or expanding without bound.

## 10. Run quick or run deep — never in between

Use a **quick check** to decide whether actionable work exists. Use **deep work**
to carry an accepted row through verification. Do not report setup, a partial
read, or a child dispatch as completion. If no useful action is possible,
record the blocker and stop cleanly.

## 11. Self-extending plans with judgment

Add newly discovered work when it is supported by evidence and belongs to the
mission. Reorder the queue when a dependency or risk changes. For user-visible
work, include direct visual or interaction proof when available.

## 12. Bounded recursion — know when good enough is good enough

New tasks must be necessary for the outcome, a named acceptance check, or a
material risk. Defer optional polish while required surfaces remain incomplete.
Stop when the plan's acceptance criteria are proven.

## 13. Do not invent work

When the queue drains, exit with the plan state and one cold-resume pointer.
New work enters through an explicit plan row backed by evidence; an idle cycle
does not silently expand scope.

---

## Quick Check / Deep Work

**Quick check** (`quick_check`) is read-only. It reads the plan and current
revision, then selects an actionable row or records why none exists.

**Deep work** (`deep_work`) advances a claimed row until its proof is green, the
row is blocked with a concrete resume condition, or available context no longer
supports safe progress.

> Scripts and JSON output use `quick_check` and `deep_work` as gate/mode identifiers.

### Every agent is a worker

Every lane produces a useful artifact: a verified change, cited finding, or
bounded blocker. Read-only reviewers do not claim implementation ownership.

### Entry Gate

Every harness starts by reading the named authority and checking whether a row
is actionable. Repeated blockers should be recorded once with a relation-based
resume condition rather than re-reported on every run.

---

## When Vidux is worth the overhead

Not every task needs a durable plan.

| Signal | Use |
|---|---|
| Small, reversible, single-run change | Direct work with normal repository proof |
| Multi-run or multi-owner change | Vidux |
| Material release, privacy, migration, or recovery risk | Vidux |
| Work must resume after context loss | Vidux |
| No durable decision or handoff is needed | Direct work |
