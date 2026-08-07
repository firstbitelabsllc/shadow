# Shadow — plan file grammar

Machine-readable grammar for `AGENT.md`. Every construct is a heading, list
line, or grep over `PLAN.md`. Nothing requires a registry, database, daemon,
queue, or writable board. `scripts/shadow-lint.py` is the enforcer: it runs
in the test gate and before any mode flip is honored.

## Sections, in order

```markdown
## Brief
- Project: <name>             required; the project is the grep across plans
- Mode: explore | ship        required; the only legal values
- Priority: 1-5               optional; steering-default rank
- Loop: /<skill>              only when it differs from /<project>-loop

## Tasks
### <milestone heading>       2-7 tasks + exactly one (DoD)
- [pending] <state the world reaches> ~ab12 | proof: cmd <runnable> | needs: ~cd34
- [pending] <...> ~ef56 (DoD) | proof: read <artifact/url> -> <observation>

## Deferred
- <what> | <why not now> | wake: <predicate>

## Contradictions
- <what contradicts what> | provisional winner | opened <ts>

## Progress                    append-only, newest at bottom
- <ts> ~ab12 PROOF <check> -> <observed result>
- <ts> MODE explore->ship | harness: <name>
- <ts> SPIKE ~ab12 <exploration question> | ends: <YYYY-MM-DD>
- <ts> DECISION ~ab12 keep|kill|promote -> <one line>
- <ts> STRUCT <edit> | trigger: <why>
- <ts> STEER auto <option> | <reason>
```

## Brief law

`Project:` values match `^[a-z][a-z0-9-]{1,31}$` — lowercase slug, no spaces,
no paths. Multi-repo projects repeat the same line in each member plan; the
project view is the grep across them.

## Task law

- State ∈ `pending | in_progress | blocked | completed`.
- IDs are four base36 chars (`~ab12`), unique per plan, stable across
  reordering; on a mint collision, re-mint. References always use the hash.
- Proof classes: `cmd <runnable>` (machine-rerunnable), `read <artifact/url
  -> expected observation>` (a human or agent re-reads the real surface), or
  `gate <owner> resume: <predicate>` (person-gated; closes agent-side with a
  handoff). Bare prose proof is a lint finding. No proof, no completed.
- `needs: ~hash[, ~hash]` is the only readiness gate: a task is ready when it
  is pending and every needs-target is completed. A discovered task's paired
  Progress line names its origin task.
- Every new task answers two questions before it lands: why now, and what
  does it contradict? A live conflict becomes a Contradictions row.
- A task flips completed only in the same commit as its PROOF line;
  `shadow accept --row` reruns a `cmd` proof in a clean detached checkout
  and is the only code path that flips a task.

## Milestone law

`###` heading over 2-7 tasks plus exactly one `(DoD)` task, which flips only
after every sibling. Milestone status is derived at read time, never stored.
Structural edits land with a paired `STRUCT` Progress line naming the
trigger.

## Mode law

`Mode: explore` is exploration and interrogation: spikes are opened with
`SPIKE ~hash ... | ends: <date>` and must end in a `DECISION ~hash
keep|kill|promote` line — an expired spike with no decision blocks, and
entering or holding `Mode: ship` over one is refused
(`SHIP-OVER-OPEN-SPIKE`). `Mode: ship` is entered only with a named harness,
via a `MODE` Progress line in the same commit as the mode edit. A surfaced
contradiction demotes to explore in writing.

## Ship law

Shipping appends one proof line per DoD clause — named check plus observed
result, re-observed from fresh state — or a named owner handoff with a
resume predicate. The shipping commit folds one lesson into standing
knowledge or writes `LESSON none — <why>`.

## ARCHIVE

The shipping commit moves the milestone's `###` block, its proof lines, and
its Progress lines to `docs/plan-archive/<slug>.md`, leaving one tombstone
task. Moves only; deletion and regeneration are banned.

## LINT

`scripts/shadow-lint.py`, exit non-zero on blocking findings; deterministic
across reruns. Checks: task shape; ID-DUP; NEEDS-DANGLE; NEEDS-SHAPE;
PROOF-MISSING / PROOF-CLASS / PROOF-SECRET; DOD-COUNT; DOD-EARLY;
DEFER-NO-WAKE; MODE-ILLEGAL (legacy `Spike|Defer|Challenge|Broad|Close`
values included); TS-ORDER (warning); READ-FIT (warning, lines over 2,000
chars); SECTION-MISSING (warning); SPIKE-NO-END; SPIKE-DUP;
SPIKE-EXPIRED-NO-DECISION; SHIP-OVER-OPEN-SPIKE; ORPHAN-DECISION (warning).

## BOARD

Read-only projection of `- Project:` greps. A lane groups one project's
plans; a card renders counts, the lint chip, the Contradictions count, and
the current milestone — derived at read time. An unparseable plan renders as
a red card, never best-effort counts. The moment any surface lets a viewer
write a task or schedule work, it is a banned second store.
