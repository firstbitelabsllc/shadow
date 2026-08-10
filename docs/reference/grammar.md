# Shadow — plan file grammar

Machine-readable grammar for `AGENT.md`. Project work remains headings and
list lines in `PLAN.md`; the computer root board is one bounded JSON pointer
ledger. Nothing requires a database, daemon, queue, or scheduler.
`scripts/shadow-lint.py` enforces project plans.

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

## Plan location

**Each entity's `PLAN.md` owns its milestone/checkpoint rows, proof, and
evidence.** The computer authority is the local Git repository at `~/.shadow`.
Its `board.json` groups entities under projects and owns global project
priority, claims/owners, entity pointers, and exactly one resume checkpoint id
per entity. It never stores checkpoint text, proof, milestone detail, or
evidence.

The local file wins immediately. A private remote may be pushed separately as
optional asynchronous recovery and may lag; it never gates or overrides a
local write. Same-computer writers serialize a fresh read, decision, atomic
replace, and local Git receipt under one advisory lock. Process death releases
the lock; readers see either the complete old file or the complete new file.

Every claim records `claimed_at`, `return_by`, and the fixed recovery action:
probe its proof, then adopt, park with one wake, or close it. Staleness is
derived when the board is read; no heartbeat, daemon, or automatic reassignment
exists.

Lifecycle changes are explicit transactions. `throw --adopt-expired` may
replace an overdue claim only after its proof was probed. `return --by` closes
only that owner's claim and accepts exactly three durable states: a completed
row with its PROOF receipt, a blocked row with one Deferred wake naming the
row, or an owner handback of pending/in-progress work. A healthy stored
entity-plan pointer remains the canonical local locator; another branch or
worktree cannot claim checkpoint text absent from it. During import, a
different checkout of that same identity is withheld before its body is parsed
only when exactly one registered locator is regular, bounded-readable,
grammar-clean, and otherwise healthy. Its self-demotion banner still retires
the identity. If the registered pointer breaks or aliases multiply, no
suppression applies: the candidate follows the ordinary fail-closed path.

Discovery may show a plain-directory plan as read-only material, but actionable
entities are Git-backed: claim, proof, acceptance, publication, and durable
logical identity require a committed plan snapshot. A missing or unreadable Git
context fails closed instead of silently changing identity to a local path.

A repository may declare additional plan locations in its root plan, as **one**
Brief line carrying at most **three** comma-separated globs:

```text
- Plans: plans/*/PLAN.md, skills/*/PLAN.md
```

Repo-relative only — no absolute path, `..`, leading `/`, recursive `**`, or
symlink traversal. Nothing else in the repository is scanned, so a worktree
pool, vendored copy, or archive cannot enter the board by accident.

Bounded discovery walks **project roots, not directories**: the portfolio root's
immediate children that own a `PLAN.md`, each asked for its own plan plus its
declared globs. There is no recursive search, and both each repository and the
whole import have a hard 250-plan admission budget. Overflow fails loudly; it
is never truncated. No unregistered directory outside the portfolio is scanned;
the sole external read is the exact registered `PLAN.md` pointer already stored
in this computer's board.
Import is all-or-nothing: an unreadable, malformed, oversized, symlinked, or
non-regular unknown or unsafely aliased legal candidate fails loudly and leaves
the board unchanged. The sole exception is the same-identity sibling of one
healthy registered locator described above; `shadow status --shadowed` names
that suppression with stable opaque entity/copy locators, without exposing a
checkout path or a secret-shaped directory name.

One logical entity per `(normalized origin, repo-relative plan path)`. A
worktree or clone resolves to the same identity as its main checkout and never
renders twice. The `Project:` slug groups related entities and owns their shared
global priority; every entity retains its own pointer and resume checkpoint.

Why the rule is shaped this way, measured on the reference machine 2026-08-09:
7,250 `PLAN.md` files exist under the portfolio root; a recursive scan reaches
777 of them, 665 of which are byte-identical copies of 196 originals. Repo-root
alone would be simpler, but it would orphan 36 live nested plans that real work
depends on, so the declared-glob line exists to keep exactly those visible.
Discovery is an import source, not authority. Once registered, an entity is
reached through the computer board while checkpoint facts remain only in its
plan.

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
  `shadow accept --row ... --by <seat>` reruns a `cmd` proof in a clean detached checkout
  and is the only code path that flips a task.

## Milestone law

`###` heading over 2-7 tasks plus exactly one `(DoD)` task, which flips only
after every sibling. Milestone status is derived at read time, never stored.
Structural edits land with a paired `STRUCT` Progress line naming the
trigger.

A milestone MAY carry one optional `- tools: <skills, flows, process — why>`
line directly under its `###` heading, before the first task row. It records
which skills/plugins/tooling this milestone's work actually needs — written
by whoever works the milestone, living in the plan, never in a side store
(pattern, not store). `shadow amp` projects it into the goal block; lint
ignores it.

## Dispatch law

`shadow throw` is the only public claim path. It validates the pointed entity
checkpoint and proof, then atomically records `(entity, row id, owner, claimed at,
return by, recovery action)`
in the computer board. It does not flip or copy the entity checkpoint. Two local
seats claiming one target produce exactly one winner; the loser re-reads the
persisted claim and is told its owner. `shadow status --in-flight` joins the
pointer back to entity text and proof at read time. Liveness is never asserted
—probe the entity-owned proof, never a process.

Historical `THROWN` lines, if present in an imported plan, are provenance only
and never own live claims or resume selection. Each logical entity consumes
that historical ownership at most once when it first enters the board.

`- <ts> NOTE @<lead> <text>` is how one lead addresses another. Progress is
append-only and serialized by fast-forward, so simultaneous notes are a push
race, never a lost message — but delivery is at fetch, not at keystroke.

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

The hot plan is bounded at **256 KiB**, **128 task rows**, and **32 milestone
headings**. `shadow lifecycle` reports those checked-in limits without writing
by default. An over-budget report exits non-zero; limits are product law, not
environment knobs.

`shadow lifecycle --apply --repo <entity-directory> --milestone '<exact heading>'`
moves one fully completed milestone's exact `###` block and every Progress
item referencing its ids to the `docs/plan-archive/<safe-slug>.md` adjacent to
that entity's plan. Root and declared nested entities use the same transaction;
Git pathspecs remain relative to their shared repository root. Satisfied
`needs:` references are folded, and the live block becomes one non-task
tombstone pointer, so lint and rotation no longer treat archived ids as live.
A deterministic `STRUCT` receipt names the next open milestone (or records that
none remains), so compaction never erases the rotation handoff.
The plan and archive are atomically replaced and land in one local commit with
hooks and signing disabled. Repeating that exact apply reports already archived
and changes nothing.

Apply refuses a dirty plan or target archive, symlinks, an existing archive
with different provenance, a malformed or unproven milestone, and a non-Git
plan. Worktree or snapshot retirement is unsupported until a versioned,
Shadow-owned manifest defines the exact target and deletion provenance; the
command reports that boundary and never guesses or recursively deletes.

## LINT

`scripts/shadow-lint.py`, exit non-zero on blocking findings; deterministic
across reruns. Checks: task shape; ID-DUP; NEEDS-DANGLE; NEEDS-SHAPE;
PROOF-MISSING / PROOF-CLASS / PROOF-SECRET; DOD-COUNT; DOD-EARLY;
DEFER-NO-WAKE; MODE-ILLEGAL (legacy `Spike|Defer|Challenge|Broad|Close`
values included); TS-ORDER (warning); READ-FIT (warning, lines over 2,000
chars); SECTION-MISSING (warning); SPIKE-NO-END; SPIKE-DUP;
SPIKE-EXPIRED-NO-DECISION; SHIP-OVER-OPEN-SPIKE; ORPHAN-DECISION (warning).

## BOARD

The root board is writable only through its claim/lifecycle transaction and
contains pointer metadata only. Human status and the browser dereference those
pointers and render project rows without copying them. An unparseable or
missing pointed plan fails loudly; no dashboard or scan becomes competing
authority.
