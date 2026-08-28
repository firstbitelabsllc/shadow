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

This creates new authority. There is no one-to-many project-map migration
command, and these steps do not move rows, claims, or proof out of an existing
plan.

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

Do not split a live authority in place. Current public commands do not provide
an atomic one-to-many migration across plan roots, board membership, local and
remote claims, archives, and Progress provenance.

Adopt the map safely:

1. Start each new independently steerable outcome as a new entity plan with the
   existing project slug.
2. Let existing claimed plans retain their rows and identity.
3. Use `shadow lifecycle` and the plan tree to compact their hot bytes.

Deleting rows from a claimed plan, moving active remote claim refs, or copying
proof into a child is not migration.
Quiescence is a prerequisite for a future migration design, not permission for
a manual split with today's commands.

## Rejected designs

- A canonical `project-map.json`, graph database, queue, or durable graph cache.
- Board records containing checkpoint text, proof, dependency edges, or copied
  status.
- Qualified cross-plan `needs:` added to only some parsers or commands.
- A coordinator plan that repeats child outcomes or receipts.
- Child plans minted from storage shards or historical sections.
- A live one-to-many split without quiescence, exact provenance conservation,
  and rollback.

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
  tests.test_plan_store.PlanTreeBuildTests.test_dangling_needs_refuses
```
