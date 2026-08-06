# The Method — file contract

Machine-readable grammar for `AGENT.md`'s standing behavior. Every construct
is a heading, list line, or grep over files that already exist. Nothing here
requires a registry, database, daemon, queue, or writable board. Markdown
stays the sole authority; the browser renders a read-only projection of it.

## Entity and loop

An entity is a grep result, not a file. Membership is one line in each member
plan's `## Operator Brief`:

```markdown
- Entity: resplit
- Loop: /resplit-loop
```

- `Entity:` values match `^[a-z][a-z0-9-]{1,31}$`. Multi-repo entities repeat
  the same line in each member plan; the entity view is the grep across them.
  A rollup that cannot be derived from member plans at read time is not entity
  state.
- The loop — standing knowledge of how to build, test, style, and why — lives
  where it already lives: per-repo `CLAUDE.md`/`AGENTS.md`, the entity's brand
  and loop skills, and boundary skills. `- Loop:` makes the pointer greppable;
  default is `/<entity>-loop` when that skill exists. Standing-knowledge files
  carry how-to only — never status reports or progress lines.

## Project

A project is one repo-local `PLAN.md` — today's Shadow contract plus one
brief field and three sections:

```markdown
## Operator Brief
- Entity: resplit
- Mode: Close
- Milestone: ASC resubmission accepted

## Checkpoints      <- milestones and checkpoint rows (below)
## Deferred         <- one row each: what | why-not-now | wake: <predicate>
## Contradictions   <- the two claims + which file provisionally wins
## Progress         <- append-only log, newest at bottom
```

`Mode:` is one of `Spike | Defer | Challenge | Close`; it changes only in a
cycle that writes a Progress line explaining the flip. A Deferred row without
a wake predicate is invalid. A Contradictions row leaves the section only via
a Progress line citing evidence.

## Milestone

A milestone is a `###` heading inside `## Checkpoints`:

```markdown
### M2 — ASC resubmission accepted
```

- Shape: 2–7 checkpoint rows plus exactly one row tagged `(DoD)`. The DoD row
  may flip to completed only when every sibling row is completed. One row is
  just a checkpoint; more than seven must split.
- `M<n>` ids are stable and never reused; splits mint `M2a`/`M2b`.
- Re-portioning is legal for any agent, but only inside a cycle and only with
  a paired Progress line naming the trigger (failed proof, recorded
  contradiction, deferred wake firing, or an operator steer). A milestone edit
  with no paired Progress line is corruption.
- Milestone status is derived from its rows at read time — never stored.

## Checkpoint

The checkpoint row is the unit one chief chat multiplexes across:

```markdown
- [pending] C5~k7f2 Age-rating PATCH accepted by ASC | proof: npm run asc:verify | size: M | needs: C4~a3f8
```

- State ∈ `pending | in_progress | blocked | completed` (aliases `x`, `done`,
  `working` parse).
- ID = `C<n>~<hash4>`: the ordinal is display-only and may renumber; the four
  base36 chars are minted from
  `sha256(milestone-heading|row-text|creator|timestamp|nonce)` and never
  change. References always use the hash (`needs: C3~k7f2` or bare `~k7f2`),
  so rows survive reordering and merge across branches. On a mint collision
  within the file, re-mint with the next nonce.
- The verifiable state is a world-state, never an activity. `| proof:` is the
  exact command or check whose output flips the row — no proof, no completed,
  ever. `| size:` is `S` (one sitting) / `M` (one cycle) / `L` (should be a
  milestone).
- `needs: ~<hash>[, ~<hash>]` is the only readiness gate: a row is ready when
  its state is pending, every `needs:` target is completed, and its milestone
  is not deferred or challenged. `from: ~<hash>` records discovered-from
  lineage and never blocks.

### Claiming without a queue

Many subagents may serve one checkpoint. Coordination is append-only Progress
lines with the own-row guard — re-read the file immediately before appending,
append at the bottom, never edit another seat's line:

```markdown
- 2026-08-05T15:10Z C5~k7f2 CLAIM seat=asc-1 scope="attr payload"
- 2026-08-05T16:02Z C5~k7f2 PROOF seat=asc-1 out=evidence/asc-verify.txt
- 2026-08-05T16:40Z C5~k7f2 DONE seat=asc-1
```

Only a seat holding a PROOF line for a row may flip its state, and the flip
lands in the same commit as the DONE line. Git is the arbiter: a merge
conflict on the same row or Progress line IS the collision detector. A CLAIM
with no PROOF after one full cycle is stale; the next seat supersedes it in
its own claim line. One claim per loop: a cycle drives one checkpoint to a
recorded result before claiming the next.

## PLAN-LINT (run at every mode transition; read-only)

Before honoring any mode transition, lint the plan and report — never edit:

- A. Duplication — two rows asserting near-identical state; mark the weaker.
- B. Ambiguity — vague adjectives with no measurable predicate; unresolved
  placeholders; `proof:` that is prose, not a runnable check.
- C. Underspecification — a verb with no observable outcome; missing `proof:`
  or `size:`; proof referencing targets defined nowhere.
- D. Standing-knowledge conflict (auto-CRITICAL) — a row contradicting a
  MUST/NEVER in the entity's CLAUDE.md/AGENTS.md/skills, or treating a
  person-gated item as agent-completable.
- E. Coverage gaps — an Outcome clause with zero mapped rows; a row under no
  milestone; a milestone with zero rows; a DONE line whose row does not exist.
- F. Inconsistency — terminology drift; DONE without PROOF, PROOF without
  CLAIM; `needs:` pointing at a later or missing row without a note;
  transition-law violations (Close entered with open Challenge rows, Deferred
  rows missing wake predicates, a Spike past its box with no verdict).

CRITICAL blocks the transition. Spike may bypass B and C but must exit with a
verdict. Output is a bounded findings table plus a coverage summary —
deterministic across reruns.

## CLOSE — DoD coverage matrix and lesson delta

Close appends one line per DoD clause under `### Close` in Progress:

```markdown
- DOD d1 guest opens trip link cold | C: ~k7f2,~b44c | proof: npm run e2e:triplink -> 12/12 @ abc123f | status: Verified
```

- Legal statuses: `Verified | Failed | Unknown | LEO-GATED`. A proof value
  names an exact command, path, or URL AND an observed result; "works as
  expected" is illegal. Every line must trace to a PROOF Progress line or a
  committed artifact, else it is Unknown by definition.
- Gates, all required before the plan may close: no open CRITICAL/HIGH lint
  finding; zero Unknown lines (LEO-GATED only with a named handoff and resume
  predicate); every proof re-runs from origin-fresh state; changed core files
  map to at least one row; the work follows the entity's standing knowledge;
  no secrets in any proof line.
- The lesson delta is the final Close artifact: fold what the work taught into
  the entity's standing knowledge (complete replacement text under the target
  heading, never a diff), or append one explicit `LESSON none — <why>` line.
  Folding is verified by re-reading the target file; a delta that cannot be
  applied cleanly stops the close rather than dropping content.

## Steering

Steering is a prompt shape, not a system. At natural boundaries (a checkpoint
closed, a goal chained) the chief greps the top ready rows across entities,
ranks by entity priority, mode (Close outranks Spike), and DoD adjacency, and
offers:

```text
STEER <date>
A) resplit ~k7f2 — Age-rating PATCH accepted by ASC (M, Close)
B) snowcubes ~c9d1 — Storefront shows both new flavors live (S, Close)
C) shadow ~e2a7 — Method contract tests green on main (S, Close)
D) You write it.
Default if silent: A
```

The moment any surface lets a steering choice write a row or schedule work
directly, it has become a second queue and is banned; choices flow back only
as the chief editing the owning plan.

## Board

The loopback browser renders entities as lanes and plans as cards — mode chip,
current milestone, checkpoint counts, state, and whether a decision is
waiting. It is a read-only projection: counts only, zero write surfaces, one
interactive element (card select into the existing brief view). Board fields
are closed vocabularies or pass the same privacy gates as plan titles.
