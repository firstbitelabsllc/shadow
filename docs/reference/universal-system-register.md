# Universal-system decision register — M20

Every requirement raised in the two seats' chats (2026-08-09 → 2026-08-10),
folded durable. Each entry is adopted, rejected with its reason, or deferred
with an exact wake. Nothing about this milestone may remain chat-only: a
seat that finds its chat missing here appends, it does not assume.

Sources: `owner` (the directing person; directives dated, not quoted), `claude-seat`, `codex-seat`.
"Lands in" names the M20 row or surface that carries the decision.

## Adopted

1. **One root board per COMPUTER; project plans stay authoritative shards.**
   owner directive (2026-08-10): the computer, not the repository, is the
   portfolio authority boundary — and equally, projects and milestones keep
   their own plans; the board is not a monolith. The board owns priority,
   claims, owners, and one resume pointer per project; shards own their
   rows, proof, evidence. Lands in: the Contradictions entry + every M20 row.
2. **Pointers, never copies.** A task's text exists in exactly one file,
   ever; the board references, it never restates. codex-seat ("store each
   fact once") + claude-seat mechanic. Lands in: ~root.
3. **Board authority is the LOCAL `~/.shadow` git repository.** A private
   remote is optional recovery — best-effort, async, never required for a
   write to count, never live authority; recovery is only as fresh as the
   last push and that limit is stated. claude-seat proposed required
   per-write push; codex-seat corrected (2026-08-10): required push couples
   the loop to the network. Corrected form adopted. Lands in: ~root.
4. **The claim CONTRACT is single-winner plus crash recovery, mechanically
   proven.** An advisory lock reusing the installer's crash-safe write
   discipline is the implementation candidate, not the contract — any
   mechanism passing the tests satisfies it. Cooperating seats only.
   claude-seat proposal, codex-seat correction (2026-08-10) adopted:
   contract over mechanism. Lands in: ~root (the claim half of the board row).
5. **Import is bounded and provenance-preserving, consuming the shipped
   dedup and archive-veto machinery; ghost copies are excluded by
   construction.** Measured basis on the dogfood machine: 7,768 PLAN.md
   files, ~60% from one repository's ~120 never-torn-down worktrees plus
   dated snapshot clones. Lands in: ~impt.
6. **Compaction, completion, and garbage collection are a first-class
   subsystem.** owner directive (2026-08-10), ranked above all else after
   the ghost-copy measurement. Landed worktrees
   retire, snapshots expire, shipped milestones archive, hot plans compact
   without losing receipts, standing loops declare lifecycle. Lands in: ~gc20.
7. **The activation text is one invariant plus the loop and rails — no
   current work, no milestone names, byte-identical across hosts.**
   codex-seat correction, adopted over stuffing evolving philosophy into
   permanent text. The invariant: continuously find and remove the
   highest-cost waste without sacrificing release confidence. Lands in: ~actv.
8. **Shadow owns the canonical top-level directive block, written only
   through the installer's managed markers so it is iterable forever.**
   owner directive (2026-08-10): iterability is a requirement, and the
   owner's machine is the dogfood target with full-overwrite authorization
   on record for the owner's own files only; reversible because the
   installer preserves the pre-write state. Lands in: ~actv.
9. **Extension buckets filled with the fleet's best in-house operators:**
   brainstorming and code review from the superpowers plugin; design through
   /craft with /taste carrying the quality bar; delegation through shadow's
   own host-run. No external agent products; published patterns (e.g.
   Devin's) are studied into Method. owner. Correction on record: /impeccable
   was retired INTO /taste (2026-07-25) — /taste is the live name. Lands in: ~bops.
10. **Tiered verification, release-train shaped.** Feature lanes run
    declared focused checks; the trunk runs affected integration checks and
    curates test health (a trunk-cutter responsibility); release candidates
    run the full story-driven gauntlet — E2E journeys, adversarial bug bash,
    rollback proof. owner idea + codex-seat tiers + claude-seat guard:
    **declared-minimal, never silently skipped — a silent skip fails loudly
    and that failure is itself tested** (every recorded green-lie in fleet
    memory was a silent skip). Lands in: ~tier.
11. **The five-waste loop.** Hypotheses on record (repeated full validation;
    context reconstruction; ghost worktrees/plans/snapshots; repeated
    same-reasoning reviews; late release-level discovery). Findings remain
    hypotheses until measured; proven countermeasures become Method law.
    Lands in: the activation invariant + Method.
12. **Terminating audit contracts.** Findings inside a stated contract are
    blockers; findings outside it become rows — never another hold. Proven
    this session: seven audit rounds on the installer converged only after
    the contract was written. Lands in: Method.
13. **Snapshot cheap, delete now, reconcile from the snapshot.** owner
    aggression directive. A rescue branch costs one command; a migration
    plan costs a session. Lands in: Method.
14. **Seat-neutral goal + SHA handshake.** The goal prompt assigns nothing
    by name; every seat prints the goal's SHA-256 and its fetched ref, then
    claims — one writer per row. codex-seat. Lands in: the goal prompt + ~root.
15. **The goal prompt is a pointer.** owner directive (2026-08-10): the
    work is too much for a prompt. Requirements live in this register and
    the M20 rows;
    the prompt names the milestone and the rails, nothing else. Lands in:
    the goal prompt; this file is the proof of the split.
16. **Slash live legacy surfaces now.** owner directive, verbatim intent:
    remove the vidux plan convention and every live compatibility surface
    of the pre-rename product name, then reconcile. In flight — see
    In-flight state below.
17. **The fixed installer lands first.** It is the delivery vehicle for
    ~actv (writes the block through managed markers without destroying
    symlinked host files). Lands in: ~actv needs ~slnk.
18. **Two install modes, never conflated.** Strangers get the atomically
    replaceable managed block; only the owner's own host files may be fully
    overwritten as dogfood, with backup and an upgrade-converges proof.
    codex-seat (2026-08-10). Lands in: ~actv.
19. **GC has teeth.** Enforced byte/row/milestone budgets, return-by on
    every claim, finite slices with successors, dry-run-first idempotent
    cleanup, refusal to delete dirty or provenance-bearing state.
    codex-seat (2026-08-10). Lands in: ~gc20.
20. **Capability selection is amp's job and it is recorded.** Filled
    buckets alone prove nothing; `shadow amp` deterministically selects and
    records why, version, fallback, result. codex-seat (2026-08-10).
    Lands in: ~bops.
21. **M20 is the only bootstrap.** No competing branch or parallel
    milestone; corrections land as amendments to these rows. Both seats
    (2026-08-10). Lands in: this file's history.

## Rejected

1. **The machine ledger as a monolith absorbing every task** (codex-seat
   v1 framing). Rejected by owner ethos (2026-08-10): the board indexes, it
   does not absorb — and a monolith recreates the ghost-copy problem inside
   one file.
2. **"Per-repo architecture needs wholesale redesign."** Narrowed: shards
   remain authoritative for their own work; only portfolio-level authority
   moves to the board.
3. **External delegation or agent products in the loop.** owner: in-house
   only; learn from published patterns, use none of them.
4. **Evolving philosophy inside the permanent activation text.** One
   invariant only; Method versions carry the how.
5. **Closing the final rename race in the installer.** POSIX offers no
   compare-and-swap (Darwin's renameatx_np gives EXCL only for absent
   destinations, SWAP without expected identity); the honest contract is
   stated tiers — guaranteed / best-effort / out-of-scope — with the floor
   pinned by a test, not pretended closed.
6. **Hosted telemetry.** Already killed on this board (~obsv, Contradictions);
   reaffirmed: local, data-minimized only.

## Deferred

1. **Multi-machine live sharing of the board.** Wake: ~2st8 passes on one
   machine.
2. **Cursor activation.** Owned by the existing ~curs row (M15) — real
   surface proven by a cold session, or honestly unsupported. Not restated
   here.
3. **Per-repo verify.yaml rollout to product repositories.** Wake: ~tier
   fixture proof green; product pilots are separately claimed rows.
4. **The five-waste measurements.** Wake: the local telemetry half (M14)
   lands; until then the five stay labeled hypotheses.

## In-flight state

Coordination detail for in-flight lanes lives on the board rows themselves
(M15 ~slnk is in progress; the legacy-surface removal and the prior
session-closeout each have an owner and a written resume move). This public
register records decisions, not machine state.
