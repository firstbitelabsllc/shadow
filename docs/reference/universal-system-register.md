# Universal-system decision register

This register records the bounded owner decisions and live repository
contradictions that shape the universal system. Each entry is adopted,
rejected with its reason, or deferred with an exact wake. Chats are useful
leads and projections, never a second inventory or authority; a newly proven
requirement is reconciled here without claiming that every conversation can
be exhaustively mined.

Sources: `owner` (the directing person; directives dated, not quoted), `claude-seat`, `codex-seat`.
"Lands in" names the milestone row or surface that carries the decision.

## Adopted

1. **One root board per COMPUTER; entity plans stay authoritative shards.**
   owner directive (2026-08-10): the computer, not the repository, is the
   portfolio authority boundary — and equally, projects and milestones keep
   their own plans; the board is not a monolith. The board owns project and
   entity rotation, priority, claims, owners, and one resume pointer per
   entity; shards own their milestones, checkpoints, proof, and evidence. Lands in: the Contradictions entry + every
   universal-system row.
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
   dated snapshot clones. Lands in: ~gc20 (the import half of the
   board-hygiene row).
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
   owner directive (2026-08-10): iterability is a requirement. The public
   installer has one managed-marker mode. A private, one-time owner dogfood
   operation may replace the owner's own host file by reusing the same
   generated block, atomic replacement, and adjacent backup; it is not a
   second public installer mode. Lands in: ~actv.
9. **Extension buckets use compatible leaf disciplines from the fleet's best
   in-house operators.** Superpowers is never loaded wholesale: only
   brainstorming reasoning, TDD, debugging, review, and verification ideas
   are allowlisted. Its approval gate, spec/plan chain, agent dispatch, and
   execution orchestration conflict with Shadow's no-signoff and row-first
   delegation laws. Design routes through /craft with /taste carrying the
   quality bar; delegation stays in Shadow's own claimed host-run. No external
   agent products are used; published patterns are studied into Method.
   Correction on record: /impeccable was retired into /taste (2026-07-25) —
   /taste is the live name. Lands in: ~bops.
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
    the universal-system rows;
    the prompt names the milestone and the rails, nothing else. Lands in:
    the goal prompt; this file is the proof of the split.
16. **Slash live legacy surfaces now.** owner directive, verbatim intent:
    remove the vidux plan convention and every live compatibility surface
    of the pre-rename product name, then reconcile. Current execution state
    lives only on the computer board.
17. **The fixed installer lands first.** It is the delivery vehicle for
    ~actv (writes the block through managed markers without destroying
    symlinked host files). Lands in: ~actv needs ~slnk.
18. **One public install mode plus one private dogfood operation, never
    conflated.** Strangers get the atomically replaceable managed block.
    Only the owner's own host files may be fully overwritten by the private
    one-time operation, with backup and an upgrade-converges proof; no public
    flag or second installer contract exposes it. codex-seat (2026-08-10).
    Lands in: ~actv.
19. **GC has teeth.** Enforced byte/row/milestone budgets, return-by on
    every claim, finite claim and GC receipts with successors, dry-run-first
    idempotent cleanup, refusal to delete dirty or provenance-bearing state.
    Finite means each lease and cleanup run terminates; it never means the
    Outcome stops. Closing a receipt exposes and claims the next reachable
    work until full acceptance or exact hard-rail wakes.
    codex-seat (2026-08-10). Lands in: ~gc20.
20. **Capability selection is amp's job, is recorded, and never gates on an
    absent bucket.** Filled buckets alone prove nothing; `shadow amp`
    deterministically selects an installed compatible capability and records
    why, version/detail, fallback, and result. Missing, stale, or disabled
    capabilities warn and select the native host plus Shadow Method fallback;
    they never block status, install, or claim. Superpowers selection is
    restricted to the compatible leaves in decision 9. codex-seat
    (2026-08-10). Lands in: ~bops.
21. **The universal-system milestone is the only bootstrap.** No competing branch or parallel
    milestone; corrections land as amendments to these rows. Both seats
    (2026-08-10). Lands in: this file's history.
22. **Humans get outcome names, never internal codes.** Goal blocks, status,
    plan headings, documentation, and seat updates lead with descriptive
    outcomes. Milestone numbers, row IDs, branch slugs, and invented track
    names stay internal and appear only when an exact machine reference is
    requested. owner directive (2026-08-10). Lands in: the activation and
    human-language acceptance proof.
23. **Outcome completeness outranks packet size.** Drain every reachable row
    required by the Outcome, fan out safe path-disjoint claims, integrate
    their proof, and keep choosing successors. Reviewable tasks, claims, and
    focused checks are safety units, never a session, campaign, or ambition
    cap. Stop only when full acceptance is mechanically true or every
    remainder has an exact hard-rail wake. owner + codex-seat (2026-08-10),
    correcting the repeated collapse of full-product intent into a single
    campaign or slice. Lands in: Method, goal shaping, amp runtime rails,
    standing activation, init, browser, guides, and ~gc20 lifecycle law.

24. **The bar has a name: the system is an extension of its owner, and it
    is reached only through gauntlets.** owner directive (2026-08-10, on
    going to bed): the product is not done when features exist — it is done
    when the loop challenges findings, selects and uses every relevant
    installed skill, and makes the owner's calls as if the owner were
    present; and confidence comes ONLY from repeated end-to-end gauntlets —
    the whole system run against disposable mock portfolios (fake repos,
    plans, ghosts, two seats) with proof at every step — until the runs are
    boringly green. This sharpens the two-seat DoD's spirit: one passing run
    is a demo; the gauntlet repeated is the product. Lands in: ~2st8 and
    ~tier, and the Method's standing verification law.
25. **Proof starts at the first usable slice, not at release.** owner
    directive (2026-08-10): team agents attack the real verbs, run focused
    proof, and dogfood Shadow on Shadow as soon as a mechanism can be used.
    Each bounded independent review happens before the next layer expands;
    its surviving failures become repairs or owned rows immediately. Early
    green is evidence for that slice, never a substitute for the repeated
    whole-system gauntlet. Lands in: ~tier, Method, and the gauntlet order.
26. **The operating hierarchy is computer → project → entity → milestone →
    checkpoint.** owner correction (2026-08-10). A project groups related
    work across repositories. An entity is one independently steerable,
    durable plan. Its `###` milestones are bounded outcome stages; their
    task rows are claimable, provable checkpoints. The root board rotates
    every reachable entity and projects each current milestone/checkpoint;
    it never collapses a project to one opaque row or copies checkpoint text
    out of the entity plan. Lands in: root-board schema/projection, status,
    browser, amp, grammar, and the repeated gauntlet.
27. **Release is a pressure-aware project train across entities.** owner
    direction (2026-08-10): one fixed nightly verification train always runs
    to catch rot; an optional second configured daily window and an automatic
    early train run only when measured backlog pressure crosses a checked-in
    threshold. Deterministic inputs are accepted-change count since the last
    reachable release, oldest-change age, severity, and changed-path risk—not
    mood. Zero accepted changes suppresses only the early feature train, not
    nightly verification. A train validates accepted trunk changes through
    project integration, the repeated gauntlet, and a stranger-install stage.
    It records only those CI observations; merge, deployment, and live dogfood
    remain separate receipts in the owning entity plan and are never inferred
    from a green train. Failure returns to its owning checkpoint and blocks
    unrelated entities only when an explicit dependency requires it. Lands in:
    ~tier, Method, release fixtures, and the repeated gauntlet.

28. **Cursor support is split honestly at the surface boundary.** Cursor's
    skill mount and sealed native `shadow host run` path are supported. Cold
    directive activation is unsupported because Cursor has no reviewed,
    writable user-rule file surface on this machine; Shadow does not invent a
    `.cursor/rules` convention or tell the operator to verify it by hand. Wake:
    Cursor documents a real user-rule surface that survives a cold-session
    proof. Lands in: host verification, native-host documentation, and ~actv.

29. **Two-seat acceptance is seat-bound, identity-handshaken, and
    time-bounded.** Each real seat prints the same seat-neutral goal, its
    SHA-256, and its freshly fetched origin/main ref before claiming with one
    stable public seat name. Expected work comes from that seat's live claim,
    or its next reachable checkpoint when unclaimed, never from the first
    global resume. Board revisions are observed receipts, not values required
    to remain equal after claims. A host timeout or board drift is
    inconclusive, never green. The disposable gauntlet completes both
    disjoint rows and leaves no orphan claim. Lands in: ~2st8, host
    verification, and the repeated gauntlet.

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
2. **Per-repo verify.yaml rollout to product repositories.** Wake: ~tier
   fixture proof green; product pilots are separately claimed rows.
3. **The five-waste measurements.** Wake: the local telemetry half (M14)
   lands; until then the five stay labeled hypotheses.
