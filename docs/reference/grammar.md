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

**Claim-safety scope.** The computer board remains the local authority for
project priority, entity pointers, claims, owners, leases, and resume. The
committed entity `PLAN.md` remains the only authority for milestone and task
text, state, dependencies, proof, and Progress evidence. A remote claim ref is
only a bounded cross-computer coordination lock. It cannot rank work, supply a
task or proof, flip a row, or replace either authority.

Remote locking opts in only when the checkout's current branch configuration
names remote `origin` and a `refs/heads/` merge target. It does not require a
locally materialized remote-tracking ref. With no such configured `origin`
upstream, `shadow throw` keeps the local-only per-computer behavior above and
performs no network write. In the opted-in case, the one conventional lock is
`refs/heads/shadow/claims/v1/<entity-id>/<row-id-without-tilde>`. Shadow first
takes the exact local board claim, then creates that ref or compare-and-swaps
its observed tip, and emits the work packet only after the intended acquired
tip is confirmed. The claim commit makes the exact committed PLAN source it
names reachable without updating the tracked upstream or protected trunk.

The ref is an append-only acquired/released/completed lifecycle. Public verbs
never delete it and never reuse an absent name after a tombstone. `shadow
return` appends the released tombstone before releasing the exact local claim;
a later throw appends a new acquired child. `--adopt-expired` takes an exact
local claim, verifies the observed remote `return_by` is overdue, and CASes a
new acquired child rather than overwriting history. `shadow accept` commits and
publishes the paired PLAN completion first, appends the completed tombstone,
and then releases the exact local claim. For a remotely coordinated claim,
`shadow accept --no-push` deliberately retains the local claim and acquired
remote lock: other computers cannot be told completion is durable when the
completed PLAN was not published.

Ordinary `shadow status` derives the exact conventional refs only for the
bounded row ids in each registered local PLAN, authenticates their receipt and
named PLAN source, and projects active owners without writing them into the
computer board. It never scans arbitrary remote branches. An unavailable or
unauthenticated remote observation makes that entity status unknown instead of
calling the row reachable; retry when the configured origin can be read.

Every remote transition is create/CAS against one expected object id. After a
nonzero, timeout, or disconnected result, Shadow reads the exact ref again:
the intended object is success, the unchanged predecessor is confirmed
failure, and another valid object is a lost race. If the tip cannot be read and
validated, the result is ambiguous: no packet is emitted and the exact local
claim is retained for an idempotent retry. A confirmed loss or confirmed
failure compensates only the exact local claim created by that attempt.

The configured Git server must allow the caller to create and fast-forward-CAS
the `shadow/claims/v1/` branch namespace. A protected `main` stays protected;
repositories whose ruleset blocks the coordination namespace fail closed and
emit no packet. Granting this narrow ref permission grants no permission to
update the tracked branch and does not make the ref a project queue.

**Discovery is a separate, explicit step.** The coordination ref above decides
who may work a row, but a second computer only finds that decision if it knows
to look at the ref. `shadow throw --cross-computer` is the explicit fleet form
for a GitHub-backed entity: after the local transaction and the remote
coordination CAS, it derives one isolated commit from the exact remote-trunk
PLAN object, pushes one deterministic create-only claim branch, opens or reuses
one draft pull request, and reads back that the PR is open, draft, targets the
trunk, and names the exact claim commit. Only then may it emit the goal. The
caller's PLAN bytes, index, branch, and HEAD never move. A branch without that
PR readback is recoverable residue, not a remotely reachable dispatch, and
emits no goal; a lost create-only branch race releases both the remote
coordination ref and the exact local claim. The PR transports the PLAN receipt;
it does not become another task or claim authority. Ordinary throws do not pay
that publication cost.

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
by default. A budget-only over-limit report exits non-zero; a preview that
proves one legal monotonic repair exits zero so its CAS can be applied. Limits
are product law, not environment knobs.

`shadow lifecycle --repo <entity-directory> --milestone '<exact heading>'`
makes no change and emits a content CAS. Repeating that command with
`--apply --expect <cas> --by <seat>`
moves one fully completed milestone's exact `###` block and every Progress
item referencing its ids to the `docs/plan-archive/<safe-slug>.md` adjacent to
that entity's plan. Root and declared nested entities use the same transaction;
Git pathspecs remain relative to their shared repository root. Satisfied
`needs:` references are folded, and the live block becomes one non-task
tombstone pointer, so lint and rotation no longer treat archived ids as live.
A deterministic `STRUCT` receipt names the next open milestone (or records that
none remains), so compaction never erases the rotation handoff. If the plan is
still over a limit, an apply is legal only when every already exceeded
dimension is non-increasing, at least one exceeded dimension shrinks, and no
previously safe dimension crosses its limit; the next lifecycle pass remains
the successor. Once the
plan is within every limit, the operation records the first reachable row or
`null`, then reconciles the entity and claims that exact row for the named seat
when it is still reachable and unclaimed.
The plan and archive use same-directory atomic replacement and land in one local
commit with hooks and signing disabled. An interrupted half-state is recoverable
only when every surviving byte regenerates exactly from the original CAS. The
live tombstone and archive header carry the same SHA-256 body digest, source
HEAD, PLAN blob, operation CAS, and operation-bound successor row. Repeating the
exact apply with its original CAS validates the unique lifecycle introduction,
reports already archived, and never advances to another row; committed
marker-preserving tampering refuses.

Apply refuses a dirty plan or target archive, symlinks, an existing archive
with different provenance, a malformed or unproven milestone, and a non-Git
plan. Normal lint, portfolio import, and claim paths enforce the same hot-plan
limits before mutating the computer board; lifecycle is the repair door.

Worktree and snapshot deletion use the strict
`schemas/retirement-manifest.v1.json` contract. The command never discovers a
target. Every manifest path uses its canonical absolute spelling and no path
component may be a symlink. A worktree manifest pins one registered non-primary linked
worktree, its exact HEAD, and the authority ref that already contains it. A
snapshot manifest pins one immediate child of a canonical root, the same
logical entity, exact HEAD, UTC expiry, and a recovery ref in the authority
repository. Dry run refuses staged, tracked, untracked, ignored, conflicted,
and dirty submodule state; proves exact identity, recoverability, and a
non-symlink, non-authority target; then emits a CAS. Linked worktrees containing
any submodule are intentionally ineligible because Git cannot remove them
safely without force; clean snapshots may contain submodules.
Apply rechecks those facts
under the project lifecycle lock, writes a private crash journal, removes a
linked worktree without force or quarantines then deletes the exact snapshot
inode, and commits a path-free receipt containing the operation-bound successor
row in the entity plan's adjacent `docs/plan-archive` retirement-receipt
directory. Missing, dirty, unlanded, unexpired, moved,
replaced, broad, or provenance-bearing targets refuse without mutation.

## LINT

`scripts/shadow-lint.py`, exit non-zero on blocking findings; deterministic
across reruns. Checks: task shape; ID-DUP; NEEDS-DANGLE; NEEDS-SHAPE;
PROOF-MISSING / PROOF-CLASS / PROOF-SECRET; DOD-COUNT; DOD-EARLY;
DEFER-NO-WAKE; MODE-ILLEGAL (legacy `Spike|Defer|Challenge|Broad|Close`
values included); TS-ORDER (warning); READ-FIT (warning, lines over 2,000
chars); HOT-PLAN-BYTES; HOT-PLAN-ROWS; HOT-PLAN-MILESTONES;
SECTION-MISSING (warning); SPIKE-NO-END; SPIKE-DUP;
SPIKE-EXPIRED-NO-DECISION; SHIP-OVER-OPEN-SPIKE; ORPHAN-DECISION (warning).

## BOARD

The root board is writable only through its claim/lifecycle transaction and
contains pointer metadata only. Human status and the browser dereference those
pointers and render project rows without copying them. An unparseable or
missing pointed plan fails loudly; no dashboard or scan becomes competing
authority.
