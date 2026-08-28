# Project maps

A large Shadow project is a map of authoritative entity plans. The map already
exists in the computer board: every entity with the same `Project:` slug shares
one priority while retaining its own pointer, resume checkpoint, claims, and
plan-owned truth.

Board membership is the project map.

```text
computer board
└── project: voiceml
    ├── entity plan: engine decision
    ├── entity plan: Auto Captions ingress
    └── entity plan: serving capacity
```

Each member Brief repeats `- Project: voiceml`. When several member plans live
inside one repository, its root plan declares those locations with bounded
`- Plans: plans/*/PLAN.md` globs. Running
`shadow status --root <portfolio-root> --by <seat>` registers every declared
entity pointer and shows the bounded seat view: every member that seat owns, or
one reachable next move when it owns none. It does not load a project rollup.

To add a new sibling in one repository:

1. Add a bounded `- Plans: plans/*/PLAN.md` glob to the root plan's Brief.
2. Create a regular `plans/<entity>/PLAN.md` whose Brief repeats the root
   plan's `Project:` slug and whose rows and proof belong only to that outcome.
3. Run `shadow lint PLAN.md plans/<entity>/PLAN.md` from the repository root.
4. Commit the root declaration and nested plan together.
5. Register both entity pointers with
   `shadow status --root <portfolio-root> --by <seat>`.

This creates new authority. These steps do not move rows, claims, or proof out
of an existing plan.

To split one existing local-only monolith into the existing root plus one new
child, use the guarded migration command instead of editing board state:

```bash
shadow plan map-migrate /ABS/PLAN.md --dry-run \
  --target-ref map-target \
  --child plans/child/PLAN.md

shadow plan map-migrate /ABS/PLAN.md --apply \
  --expect TRANSACTION_SHA256 \
  --receipt /ABS/project-map-migration.json \
  --target-ref map-target \
  --child plans/child/PLAN.md
```

Dry-run is mandatory and writes nothing. `map-target` must resolve to one
direct child commit of the current source HEAD. That commit may change only
the root `PLAN.md` and one new child `PLAN.md`; the root must declare the child
through `Plans:`. Every source task row must appear byte-for-byte in exactly
one target plan. Routing is derived from that target-plan membership rather
than accepted from the caller. Plan-local `needs:` edges cannot cross the
split. `Contradictions` and `Progress` bullets must be conserved exactly and
stay with the entity named by their row ids.

Apply requires the dry-run transaction digest and a new canonical absolute
receipt path outside the repository. It is available only when the source is
the exact registered board authority, the checkout is clean, and the current
branch is verified local-only. Before either Git or board mutation, apply
writes and syncs an immutable `phase: prepared` receipt. The Git branch then
fast-forwards to the exact prepared commit before one board compare-and-swap
adds the child entity, moves mapped live claims without changing their owner or
timestamps, and selects one resume row per entity. Project identity and shared
priority do not change. The receipt remains byte-identical after success; the
JSON result reports `action: applied` and an `applied_sha256` equal to the
prepared transaction digest.

If the process stops after writing the receipt or after the Git fast-forward,
rerun the same apply command with the same receipt and digest. It validates
whether the checkout is at the exact source or target HEAD, completes only the
missing board transition, and refuses every other state.

Rollback is equally explicit:

```bash
shadow plan map-rollback /ABS/PLAN.md --apply \
  --expect APPLIED_SHA256 \
  --receipt /ABS/project-map-migration.json
```

Rollback refuses if the applied Git head, plans, board bytes, claims, priority,
or board journal changed. Before mutation it writes and syncs the immutable
`/ABS/project-map-migration.rollback.json` sidecar. On an exact match it resets
the branch to the exact original source HEAD, restores the original monolith
and board authority, moves child claims back to the root, and removes the
child. If the process stops after the Git reset, rerun the same rollback command.
Exact completed retries are no-ops and neither receipt is rewritten.

This command is intentionally not a general graph editor. It migrates exactly
two resulting entities—the existing root and one new child—and it does not
move archives, remote claim refs, plan-tree shards, or a remote-managed branch.

There is no project-map file, coordinator database, copied rollup, or parallel
status store. A project-wide integration outcome may have its own entity plan
only when it owns distinct acceptance work; it may not mirror child rows,
states, or proof.

## Two different scaling boundaries

| Boundary | What it solves | Authority |
|---|---|---|
| Plan tree | Large bytes and long history inside one logical plan | One entity plan reconstructed from content-addressed objects |
| Project map | Independently steerable outcomes that should not freeze each other | Several entity plans grouped by one board project |

Storage shards are not work lanes. Creating more plan-tree objects never
creates another owner, claim, resume checkpoint, or outcome.

## Split test

Create another entity plan only when every answer is yes:

1. The outcome can block, ship, reopen, and prove itself without freezing its
   siblings.
2. It has one distinct acceptance surface; checkpoint ownership remains in
   board claims.
3. Its checkpoints and Progress receipts can live in exactly one plan.
4. Every `needs:` edge remains inside one plan.
5. A cold seat can understand and claim it from the board without loading a
   coordinator monolith.

If the work is only another stage of the same acceptance path, keep it as a
milestone. If only the bytes are large, keep one entity and use the plan tree.
If a receipt or dependency belongs to two candidate plans, the split boundary
is wrong.

## Cross-entity requirements

`needs:` is deliberately plan-local. Shadow does not pretend several plan
reads are one atomic dependency graph, and a cross-entity condition never makes
a consumer row ready.

When a consumer requires a producer owned by another entity, choose one honest
boundary:

- The outcomes are not independently steerable and stay in one plan when the
  consumer cannot begin until the producer completes.
- The consumer is blocked behind a `gate` or Deferred wake naming the exact
  producer condition.
- The consumer owns an integration checkpoint only when it can proceed
  independently. On a migrated plan tree, that checkpoint may call
  `shadow read`, but its proof must assert that the returned producer row is
  completed; the projection alone does not enforce ordering.

The producer row and proof remain only in the producer plan. The consumer
records its own integration observation, not a copy of the producer's state.

## Existing plans

Do not split a live authority in place by hand. Use `map-migrate` only for the
bounded local-only root-plus-one-child transaction above; it does not provide a
general one-to-many migration across remote claims, archives, or plan-tree
roots.

Adopt the map safely:

1. Start each new independently steerable outcome as a new entity plan with the
   existing project slug.
2. Let existing claimed plans retain their rows and identity.
3. Use `shadow lifecycle` and the plan tree to compact their hot bytes.
4. When an existing local-only monolith truly needs one child, prepare the
   exact two-plan commit and run `map-migrate` plus its cold apply/rollback
   proof.

Deleting rows from a claimed plan, moving active remote claim refs, or copying
proof into a child without the receipt-bound transaction is not migration.

## Rejected designs

- A canonical `project-map.json`, graph database, queue, or durable graph cache.
- Board records containing checkpoint text, proof, dependency edges, or copied
  status.
- Qualified cross-plan `needs:` added to only some parsers or commands.
- A coordinator plan that repeats child outcomes or receipts.
- Child plans minted from storage shards or historical sections.
- A live split without exact provenance conservation, board compare-and-swap,
  and receipt-bound rollback.

## Proof surface

The executable contract is protected by:

- `ProjectsGroupEntitiesWithoutCollapsingThem` — one project retains multiple
  entity identities and one shared priority, allows equal local row ids in
  disjoint entities, preserves claims and cold resume for declared siblings in
  one repository, and refuses a sibling row as a local `needs:` target.
- `TheBoardHoldsPointersNeverRowCopies` — board state contains pointers and
  claims, never task or proof text.
- `ColdSeatsResumeThroughBoardEntityIds` — a cold seat resumes the exact entity
  claim owned by that seat.
- `ProjectMapMigrationIsAtomicAndReversible` — one dry-run digest binds the
  exact source, target, derived row routing, provenance, claims, project
  priority, and board state; apply preserves cold resume, interrupted apply and
  rollback resume from immutable receipts, and successful rollback restores
  the exact source HEAD, monolith, authority, and claims.
- Plan-store tests — one entity's content-addressed shards reconstruct exactly
  and reject dangling local dependencies.

Run the focused contract with:

```bash
scripts/shadow-python.sh -m unittest \
  tests.test_root_board.ProjectsGroupEntitiesWithoutCollapsingThem.test_one_project_rotates_two_entities_with_one_shared_priority \
  tests.test_root_board.ProjectsGroupEntitiesWithoutCollapsingThem.test_one_repository_project_map_preserves_entity_claims_and_cold_resume \
  tests.test_root_board.ProjectsGroupEntitiesWithoutCollapsingThem.test_sibling_row_id_never_satisfies_local_needs \
  tests.test_root_board.TheBoardHoldsPointersNeverRowCopies \
  tests.test_root_board.ColdSeatsResumeThroughBoardEntityIds.test_status_by_keeps_every_entity_owned_by_the_seat \
  tests.test_root_board.ProjectMapMigrationIsAtomicAndReversible \
  tests.test_plan_store.PlanTreeBuildTests.test_dangling_needs_refuses
```
