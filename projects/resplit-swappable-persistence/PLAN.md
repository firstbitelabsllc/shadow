# Resplit Swappable Persistence — PLAN (Authority Store)

**Status:** PLANNING + PREWORK. Authority (2026-06-13): may do everything EXCEPT
introduce SQLite/SQLiteData. Prework must be additive, worktree-isolated, and
collision-free — product dev is live in a parallel lane. SQLiteData adapter is a
stub until Leo says go. Every artifact + prework slice gets an adversarial pass.
**Prompt file:** `prompts/swappable-persistence.prompt.md`
**Goal:** rip Resplit's domain layer free of SwiftData behind a swappable Tuist
persistence module (SwiftData today; SQLiteData + in-memory as adapters), so the
engine is replaceable and the same suite runs against every adapter. Endgame:
native CKShare sharing (see memory `resplit-ckshare-sqlitedata-decision`).

**Decision anchor:** leaning SQLiteData for the CKShare endgame; the module
boundary makes that swap (or a Core Data fallback) a one-module change, not a
180-file rewrite. Dependency risk on SQLiteData is contained by (a) the adapter
boundary and (b) a fork + upstream-tracking patch branch.

---

## NORTH STAR — Test Case Stories (TOP PRIORITY)

> 26 stories generated; capability coverage: cloudkit_sync=5, cross_adapter_parity=6, in_memory_determinism=5, sqlitedata_ckshare=2, swiftdata_parity=8.
> Each story = action → adapter capability proven → pass/fail. Full set drives Phase test plans.

| ID | Phase | Capability | Story | Pass/Fail (short) |
|----|-------|-----------|-------|-------------------|
| PS-1 | P1 | in_memory_determinism | Receipt scan + in-memory split (Phase 1 SOOC determinism) | PASS: Same settlement amounts (to ±$0.01) every run |
| PS-2 | P1 | swiftdata_parity | Folder organization with receipt cascade persistence (Phase 1 SOOC parity) | PASS: Folder + 5 receipts in same state on both reads |
| PS-3 | P2 | sqlitedata_ckshare | Live Split host session participant sync with offline queue (Phase 2 SQLiteData cross-adapter) | PASS: Host + guest participant state identical after sync, offline amounts match |
| PS-4 | P2 | swiftdata_parity | Settlement sheet payment-link export cross-adapter (Phase 2 SQLiteData parity) | PASS: Payment link URLs match (same participant IDs, amounts), settlement graph  |
| PS-5 | P3 | cloudkit_sync | CloudKit sync + CKShare (Phase 3 CKShare endgame) | PASS: CKShare zone replica syncs within 10s, participant insert replicated on fr |
| PS-6 | P3 | cross_adapter_parity | Multi-adapter receipt query (Phase 3+ cross-adapter parity) | PASS: Query results match exactly (same order, same IDs), no null pointers |
| P1.1 | P1 | in_memory_determinism | Receipt cascade delete via in-memory adapter | PASS: all children deleted synchronously in-memory. FAIL: any orphaned items/par |
| P1.2 | P1 | swiftdata_parity | Folder receipt nullify via SwiftData adapter | PASS: Receipt.folder == nil, Receipt itself remains. FAIL: Receipt deleted or fo |
| P1.3 | P2 | sqlitedata_ckshare | Person participations nullify via SQLiteData adapter | PASS: participants.person == nil on all 2 participants. FAIL: participants delet |
| P1.4 | P1 | in_memory_determinism | In-memory split+settle determinism (no CloudKit) | PASS: settle produces identical settlement state on 10 runs, zero CloudKit calls |
| P2.1 | P2 | swiftdata_parity | Receipt parity: same split across SwiftData vs in-memory | PASS: snapshots identical (settled amounts, participant balances, summary items) |
| P2.2 | P2 | cross_adapter_parity | Folder currency resolution across adapters | PASS: all adapters return EUR (majority). FAIL: any adapter returns different cu |
| P3.1 | P2 | in_memory_determinism | Live Split session state consistency on in-memory | PASS: host state deterministically matches expected final balances, all sequence |
| P3.2 | P3 | cross_adapter_parity | Live Split parity: host state on SwiftData vs SQLiteData | PASS: receipt.items, receipt.participants, settled amounts identical on both. FA |
| P4.1 | P4 | cloudkit_sync | CKShare share/accept flow on SQLiteData (two iCloud accounts) | PASS: share created, accepted, and synchronized updates appear on both accounts  |
| P4.2 | P4 | cloudkit_sync | CKShare participant list parity post-accept | PASS: all 3 participants present, displayName and identityKey fields match origi |
| P5.1 | P3 | cross_adapter_parity | Receipt cascade delete across all adapters | PASS: all 3 adapters cascade-delete in same pattern (children deleted first, roo |
| P5.2 | P3 | cross_adapter_parity | Folder + Receipt + Items snapshot parity (in-memory → SwiftData → SQLiteData) | PASS: snapshots binary-identical across all adapters (count, IDs, relationships, |
| story-001 | P2 | in_memory_determinism | In-Memory Deterministic Receipt Split → Settlement Flow | PASS: flow completes identically on 10 sequential runs with same input |
| story-002 | P3 | swiftdata_parity | Receipt Cascade-Delete Graph Identical Across Adapters | PASS: SwiftData adapter ✓ zero orphans + in-memory adapter ✓ zero orphans + SQLi |
| story-003 | P3 | cross_adapter_parity | Live Split WebSocket Real-Time Participant State Sync Across Adapters | PASS: in-memory → final state matches golden snapshot. SwiftData → same final st |
| story-004 | P3 | swiftdata_parity | Folder Cascade on Unarchive; Receipt Orphan Adoption Identical Across Adapters | PASS: SwiftData adapter — receipts invisible during archive, visible after unarc |
| story-005 | P4 | swiftdata_parity | Observation Layer Cutover: @Query Subscriber List Identical Pre/Post Migration | PASS: pre-cutover snapshot == post-cutover snapshot byte-for-byte. No list jumpi |
| story-006 | P1 | swiftdata_parity | Schema Migration Safety: No Data Loss Across SwiftData → SQLiteData Transition | PASS: 100 receipts → 100 receipts (zero loss). Foreign keys intact. ReceiptItem  |
| story-007 | P2 | cloudkit_sync | CloudKit Sync Parity: Private-DB Receipt Mutation → All Adapters Observe Same Event Sequence | PASS: SwiftData → CloudSyncEventSnapshot recorded + Receipt persisted ✓. In-memo |
| story-008 | P5 | cloudkit_sync | Two-iCloud-Account CKShare Share/Accept/Edit Flow on SQLiteData Adapter | PASS: Device A + Device B both see final item amount. No merge conflicts. CKShar |

---

## Done-State (PLANNING — agent-checkable, no human gate)
Planning is COMPLETE when ALL true:
1. Test Case Stories section ≥8 grounded stories + adapter-capability matrix.
2. Queue rows' summed ETA ≥ **8h**, each with acceptance criteria, disjoint
   write scope, ETA, dependency order.
3. All coverage sections present + concrete (real paths/modules): phase map,
   Phase-0 safety net, Tuist graph, observation layer, migration, pre-mortem,
   CKShare/SQLiteData fit + fork strategy, risk register.
4. No SQLite/SQLiteData dependency introduced; prework is additive +
   worktree-isolated + collision-free with the parallel product-dev lane.
**Exit-on-refire:** all four true + no new planning gap → exit, don't loop.
Execution is a separate goal Leo launches deliberately.

---

## Phase Map (multi-phase, checkpoint-gated)

Every phase ends at a CHECKPOINT that must be green before the next begins.
**No persistence file moves until Phase 0's safety net is green.**

- **Phase 0 — Safety net FIRST (prework, no migration).** Characterization +
  regression + UI tests proving current behavior is locked. Ground on the
  existing surface: 337 XCTest files, 74 `Autobot*` UI selectors, 10 snapshot
  tests, 24 in-memory configs. Inventory coverage, find gaps around the 6 core
  models + Live Split + CloudKit, add characterization tests + golden snapshots.
  _Checkpoint 0: baseline suite green + coverage map signed off._
- **Phase 1 — Contract module (no behavior change).** Define
  `ResplitPersistenceContract` (protocols + plain domain types), no adapter
  wired yet. _Checkpoint 1: builds, app still on SwiftData, suite green._
- **Phase 2 — First vertical slice.** One entity end-to-end through the
  contract behind a SwiftData adapter; parallel-run vs direct SwiftData.
  _Checkpoint 2: slice green on both paths, snapshots identical._
- **Phase 3 — Adapters.** SwiftData + in-memory + SQLiteData adapters conform;
  run the Phase-0 suite against each. _Checkpoint 3: suite green ×3 adapters._
- **Phase 4 — Observation cutover.** Replace `@Query` in 7 view sites with the
  contract's observation API. _Checkpoint 4: UI snapshots identical._
- **Phase 5 — CKShare on SQLiteData + fork-tracking.** _Checkpoint 5:
  two-device share story green._
  _[fleet-pending: per-phase rows, gates, and ETA below.]_

---

## Design — judged winner (fleet w2pmacqy6, unanimous 3/3)

> **AMENDED by red-team (see "Design Red-Team Findings" below):** only 2 real `@Query` sites (not 7); SOOC is SCOPED not whole-graph; a CloudKit remote-change bridge is a Phase-1 contract requirement.

**Chosen: hybrid.** "Store-Owned Observable Collections (SOOC)" as the shippable
Phase-1 spine — the store owns identity/persistence and publishes live
collections views subscribe to, so `@Query`/`ModelContext` leaves the 7 view
sites without a behavior change. **"Records-and-Resolvers"** (plain value-type
`Record` structs + a `Filter`-enum query spec) is adopted as the SQLiteData/GRDB
endgame read model. Design 1's full value-type domain is deferred to a
post-launch phase. Census found **15 load-bearing blockers** to sever.

### Tuist Module Graph — SOOC + Records Hybrid

> Grounded against `/Users/leokwan/Development/resplit-ios/Project.swift` (13 targets) and `/Users/leokwan/Development/resplit-ios/Workspace.swift` (single project `.`, schemes only). Module names, bundleId prefix (`com.superfit.*`), `deploymentTargets: .iOS("26.0")`, and `product: .framework` shape are copied from the live manifest, not invented.

### Design intent (why these modules exist)

The whole point of the hybrid is **one swap seam, swapped exactly once at the composition root**. Today the persistence seam already exists — `ResplitPersistence/API/Database.swift` defines `public protocol DatabaseType`, and `ResplitCore/DI/Container+Database.swift` is the single place that constructs `Database(container:)`. But that seam **leaks SwiftData**: `DatabaseType` mentions `ModelContainer`, `ModelContext`, `PersistentModel`, and `FetchDescriptor` in its signatures. That leak is why 180 files `import SwiftData` and why `@Query`/`ModelContext` reach the 7 view sites.

The module work is therefore: **extract a SwiftData-free contract module, demote the SwiftData implementation to one of N interchangeable adapter modules, and rewire the composition root to bind exactly one adapter.** Phase 1 (SOOC) keeps the SwiftData adapter as the live binding so the 7 `@Query` view sites change behavior **zero**. Phase 2 (Records-and-Resolvers) adds a second adapter (SQLiteData/GRDB) behind the *same* contract for the CKShare endgame, selected by flipping one Factory registration.

### New modules

| Module | product | bundleId | Depends on | Role |
|--------|---------|----------|------------|------|
| **`ResplitPersistenceContract`** | `.framework` | `com.superfit.ResplitPersistenceContract` | `ReceiptSplitter` (Record value types only) | The SwiftData-free seam. Owns `StoreType` (the SOOC store protocol — owns identity + publishes live `ObservableCollection`s), the `Record` value structs (`ReceiptRecord`, `ParticipantRecord`, `ItemRecord`, `SummaryItemRecord`, `PersonRecord`, `FolderRecord`), and the `Filter` query-spec enum. **No `import SwiftData` anywhere in this module — that is the load-bearing invariant.** |
| **`ResplitPersistenceSwiftData`** | `.framework` | `com.superfit.ResplitPersistenceSwiftData` | `ResplitPersistenceContract`, `ReceiptSplitter` (`@Model` types + `ResplitSchema`), CloudKit | Phase-1 live adapter. Wraps the existing `Database`/`DatabaseType` facade and `ResplitSchema.versioned`/`.migrationPlan`. Translates `Filter` → `FetchDescriptor`, maps `@Model` → `Record`, owns `NSPersistentCloudKitContainer` private sync. This is where today's `ResplitPersistence` body migrates. |
| **`ResplitPersistenceMemory`** | `.framework` | `com.superfit.ResplitPersistenceMemory` | `ResplitPersistenceContract`, `ReceiptSplitter` (Record types) | Test/preview adapter — pure in-memory dictionaries keyed by stable id, no SwiftData, no CloudKit. Replaces today's `useTestDatabase()` in-memory `ModelContainer` for the 24 `cloudKitDatabase:.none` / `isStoredInMemoryOnly:true` test configs that don't actually need SwiftData semantics, and backs `ResplitPreview` fixtures. |
| **`ResplitPersistenceSQLiteData`** | `.framework` | `com.superfit.ResplitPersistenceSQLiteData` | `ResplitPersistenceContract`, `ReceiptSplitter` (Record types), `.package(product: "SQLiteData")` *(or GRDB)* | Phase-2 endgame adapter (Records-and-Resolvers read model). Resolves `Filter` against SQL, returns `Record` values, owns the CKShare path. **Added but NOT bound in Phase 1** — its presence must not pull GRDB into the app binary until the composition root selects it. |

`ResplitPersistence` (the existing target) is **retired in name**: its `API/Database.swift` content splits into `ResplitPersistenceContract` (the protocol, made SwiftData-free) + `ResplitPersistenceSwiftData` (the `Database`/`DatabaseSnapshotReader` implementation). Keep the `ResplitPersistence` target as a thin umbrella that re-exports `ResplitPersistenceContract` only if grep shows external `import ResplitPersistence` sites are cheaper to keep than to rewrite; otherwise delete it and rewrite imports. **Decision: keep the umbrella for Phase 1** to bound blast radius (15 load-bearing blockers + 111 `ModelContainer` refs), retire it in Phase 2.

### `Project.swift` target shape (new entries)

Insert alongside the existing framework targets, copying the live shape (`destinations: [.iPhone, .iPad]`, `deploymentTargets: .iOS("26.0")`, `infoPlist: .default`):

```swift
// Persistence Contract — SwiftData-free seam (the swap point)
.target(
  name: "ResplitPersistenceContract",
  destinations: [.iPhone, .iPad],
  product: .framework,
  bundleId: "com.superfit.ResplitPersistenceContract",
  deploymentTargets: .iOS("26.0"),
  infoPlist: .default,
  sources: ["ResplitPersistenceContract/**/*.swift"],
  dependencies: [
    .target(name: "ReceiptSplitter") // Record value types only
  ]
),

// SwiftData adapter — Phase-1 live binding
.target(
  name: "ResplitPersistenceSwiftData",
  destinations: [.iPhone, .iPad],
  product: .framework,
  bundleId: "com.superfit.ResplitPersistenceSwiftData",
  deploymentTargets: .iOS("26.0"),
  infoPlist: .default,
  sources: ["ResplitPersistenceSwiftData/**/*.swift"],
  dependencies: [
    .target(name: "ResplitPersistenceContract"),
    .target(name: "ReceiptSplitter")
  ]
),

// In-memory adapter — tests + previews
.target(
  name: "ResplitPersistenceMemory",
  destinations: [.iPhone, .iPad],
  product: .framework,
  bundleId: "com.superfit.ResplitPersistenceMemory",
  deploymentTargets: .iOS("26.0"),
  infoPlist: .default,
  sources: ["ResplitPersistenceMemory/**/*.swift"],
  dependencies: [
    .target(name: "ResplitPersistenceContract"),
    .target(name: "ReceiptSplitter")
  ]
),

// SQLiteData adapter — Phase-2 CKShare endgame (present, not bound)
.target(
  name: "ResplitPersistenceSQLiteData",
  destinations: [.iPhone, .iPad],
  product: .framework,
  bundleId: "com.superfit.ResplitPersistenceSQLiteData",
  deploymentTargets: .iOS("26.0"),
  infoPlist: .default,
  sources: ["ResplitPersistenceSQLiteData/**/*.swift"],
  dependencies: [
    .target(name: "ResplitPersistenceContract"),
    .target(name: "ReceiptSplitter")
    // + .package(product: "SQLiteData") once added to Project.swift `packages:`
  ]
)
```

The SQLiteData/GRDB package goes in the top-level `packages: [ ... ]` array (next to the existing `Factory`, `swift-snapshot-testing`, etc. remotes), **scoped as a product dependency on the SQLiteData adapter target only** — never on `Resplit`, `ResplitCore`, or the contract. That scoping is what keeps GRDB out of the app binary in Phase 1.

### Dependency edges — who depends on the contract vs an adapter

**The rule: everything depends on the contract. Exactly one module — the composition root — depends on the concrete adapters.**

- `ResplitCore` (ViewModels, Managers, Repositories) → **`ResplitPersistenceContract`** only. Its current `.target(name: "ResplitPersistence")` edge (Project.swift:143) is repointed to the contract. ResplitCore stops being able to name `Database`, `ModelContainer`, or `SwiftData` types — it talks `StoreType`/`Record`/`Filter`. This is the edge that lets the 7 `@Query` sites and 51 `ModelContext` refs be migrated behind the store in SOOC without ResplitCore knowing which adapter is live.
- `ReceiptSplitter` → **no persistence edge** (it has `dependencies: []` today and keeps it). It gains the `Record` value structs (siblings to the `@Model` types in `ReceiptSplitter/Models/`). The `@Model` types stay here too; `ResplitSchema.swift` stays here. Both contract and SwiftData adapter import `ReceiptSplitter` — the contract for Records, the adapter for `@Model`s + schema.
- `Resplit` (app / composition root) → **`ResplitPersistenceContract` + exactly one adapter**. Today it depends on `ResplitPersistence` (Project.swift:74); that becomes `ResplitPersistenceContract` (for the public surface) **and** `ResplitPersistenceSwiftData` (the Phase-1 binding). It does **not** depend on `ResplitPersistenceMemory` or `ResplitPersistenceSQLiteData`.
- Test targets → contract + `ResplitPersistenceMemory` (and `ResplitPersistenceSwiftData` only where a test genuinely exercises real SwiftData/CloudKit semantics, e.g. migration tests). `ResplitCoreTests` (Project.swift:182) repoints its `ResplitPersistence` edge to `ResplitPersistenceContract` + `ResplitPersistenceMemory`. The 24 in-memory/`cloudKit:.none` configs split: pure-logic ones move to the Memory adapter; SwiftData-behavior ones keep the SwiftData adapter with `isStoredInMemoryOnly`.
- `ResplitDevApp` / `ResplitPreview` → contract + `ResplitPersistenceMemory`. DevApp keeps its UI-facing edges (`ResplitCore`, `ResplitDesignSystem`, `ResplitUI`) and gets fixtures through the Memory adapter via preview seams.
- `ResplitDesignSystem`, `ResplitUI` → **no persistence edge** (unchanged; they're pure UI/tokens).

```
ReceiptSplitter (@Model + ResplitSchema + Record structs)
        ▲                         ▲
        │                         │
ResplitPersistenceContract  ◄─────┤  (StoreType, Record, Filter — NO SwiftData)
   ▲    ▲    ▲    ▲               │
   │    │    │    └──────────── ResplitPersistenceSwiftData  ──┐ (live Phase 1)
   │    │    └───────────────── ResplitPersistenceMemory       │  each adapter
   │    └────────────────────── ResplitPersistenceSQLiteData ──┘  imports the contract
   │
ResplitCore ──► contract only (no adapter, no SwiftData)
   ▲
   │
Resplit (app) ──► contract + ResplitPersistenceSwiftData   ◄── THE ONLY place an adapter is bound
```

### Composition-root wiring — exactly one adapter

The composition root is `ResplitCore/DI/Container+Database.swift` (the live Factory container). It is the **only** module that constructs a concrete adapter. The change:

1. The contract gains a `StoreType` Factory (alongside / eventually replacing the `database: Factory<any DatabaseType>` at `Container+Database.swift:121`). `ResplitCore` declares `var store: Factory<any StoreType>` but the **default registration lives in `Resplit` app bootstrap**, not in ResplitCore — because ResplitCore must not import any adapter.
2. In `Resplit` app startup (where `ResplitApp` already registers analytics), register the single live adapter:

   ```swift
   // Resplit app target — the ONE binding site
   import ResplitPersistenceContract
   import ResplitPersistenceSwiftData   // the only adapter import in the app

   Container.shared.store.register {
     SwiftDataStore(                       // wraps existing Database(container:)
       container: Container.shared.modelContainer()   // ResplitSchema.versioned + migrationPlan
     )
   }
   ```

3. The existing `modelContainer` Factory (`Container+Database.swift:64`, with its CloudKit/test-mode branches and `ResplitSchema.versioned` + `ResplitSchema.migrationPlan`) **stays inside the SwiftData adapter's wiring** — it's a SwiftData detail, so it moves out of the generic container and into adapter-owned registration. CloudKit (`ResplitCore/Persistence+CloudKit/CloudKitManager.swift`, `NSPersistentCloudKitContainer`) is a SwiftData-adapter concern in Phase 1.
4. Test/preview swaps reuse the existing override pattern (`useDatabase(_:)` / `useTestDatabase()` at `Container+Database.swift:574/619`), generalized to `useStore(_:)`:
   - Unit tests: `Container.shared.store.register { InMemoryStore() }` (Memory adapter).
   - Phase-2 cutover: change the **one** line in app bootstrap to `SQLiteDataStore(...)`. No other file changes. That single-line swap is the entire thesis of the hybrid.

The invariant a lint should pin (extends the existing `tools/lint/` family): **no `import ResplitPersistenceSwiftData` / `...Memory` / `...SQLiteData` outside the app target, test targets, and preview seams** — and **no `import SwiftData` inside `ResplitPersistenceContract`**. This is the structural guarantee that "exactly one adapter is bound" can't silently rot (the fix-rot pattern `wiring-regression-lint.sh` already guards elsewhere).

### Tuist best-practices implications

- **`tuist generate --no-open` after every `Project.swift` edit** (already the repo workflow step 1). Adding 3–4 framework targets is a graph change; regenerate before building.
- **Focused generate / `tuist generate <Target>`**: with the contract isolated, an agent working only on ResplitCore logic can `tuist generate ResplitCore` and pull `ResplitPersistenceContract` + `ReceiptSplitter` as the only persistence-side dependencies — the SwiftData/SQLite/Memory adapters and the GRDB package are **pruned from that focused graph entirely**. Today, because `ResplitPersistence` leaks SwiftData into everything, no focus boundary is possible. This is a concrete generate-speed and incremental-build win, not just hygiene.
- **Binary cache implications**:
  - `ResplitPersistenceContract` is small, leaf-adjacent, and changes rarely → it caches as a stable binary and stops being recompiled on every ResplitCore edit. High cache-hit value.
  - **Critical**: keep the SQLiteData/GRDB package dependency OFF the contract and OFF ResplitCore. If GRDB were a transitive dependency of the contract, **every** module downstream of the contract would invalidate its binary-cache hash whenever the GRDB package version moved — dragging a heavy SPM dependency through the whole graph. Scoping the package to the `ResplitPersistenceSQLiteData` target alone means only that one (Phase-2, unbound) framework carries the GRDB cache cost in Phase 1.
  - The SwiftData adapter inherits the CloudKit entitlement-sensitive build settings; it does NOT need the app's entitlements (those stay on `Resplit`), so it remains independently cacheable.
  - Adapters are interchangeable at the binary-cache level: because each adapter depends only on the contract + Records, swapping the bound adapter at the composition root does **not** invalidate ResplitCore's or any feature module's cached binary — only the app target (the binding site) and the newly-bound adapter recompile. This is exactly the "build-once-test-many" property the `bigapple` parallel-agent workflow wants.
- **Selective testing**: with the Memory adapter carrying the pure-logic test surface, `tuist test "ResplitCore Unit Tests"` stops depending on a real `ModelContainer` for the bulk of tests → faster, no CloudKit-account flakiness, and Tuist's selective-testing analytics can skip persistence-adapter tests when only contract/Record code changed.
- **Schemes/`Workspace.swift`**: no `Workspace.swift` change needed — it only defines `Resplit Debug`/`Release` run schemes over the `Resplit` target. The new framework targets get auto-schemes from `automaticSchemesOptions` defaults or explicit framework schemes mirroring the existing `ResplitCore Framework` / `ReceiptSplitter Framework` scheme pattern in `Project.swift` if per-module test plans are wanted (recommend adding a `ResplitPersistenceContract Framework` scheme for fast contract-only test runs).

### Migration ordering (so blast radius stays bounded)

1. Create `ResplitPersistenceContract` with `StoreType` re-exposing today's `DatabaseType` surface verbatim (still SwiftData-typed) → no behavior change, just a new target. Build green.
2. Move `Database`/`DatabaseSnapshotReader` into `ResplitPersistenceSwiftData`; `ResplitPersistence` umbrella re-exports the contract. Repoint ResplitCore + app edges. Build green (this is the riskiest step — 111 `ModelContainer` + 51 `ModelContext` refs + 15 blockers ride here).
3. Introduce `Record` structs + `Filter` enum in the contract; SOOC store publishes `ObservableCollection`s; the 7 `@Query` view sites move behind the store with **no behavior change** (Phase 1 done).
4. Add `ResplitPersistenceMemory`; migrate the pure-logic slice of the 24 in-memory test configs.
5. (Post-launch) Add `ResplitPersistenceSQLiteData` + GRDB package; implement Records-and-Resolvers read model; flip the one composition-root line behind a flag for the CKShare endgame.

Steps 1–4 are the shippable Phase-1 spine; step 5 is deferred per the chosen architecture.

### Observation Layer (replaces @Query) — highest-risk piece

### Why this is the riskiest piece

`@Query` is the one SwiftData primitive that has **no behavioral substitute we can quietly slide in**. The other coupling axes (`ModelContext`, `ModelContainer`, `@Model`) are imperative — we can wrap them behind a facade and the call site never knows. `@Query` is *declarative and live*: SwiftData wires the view's identity into the persistent store's change graph and re-invalidates the view body on every relevant mutation **and on every CloudKit mirror import**, with zero glue code. There are exactly **3 live `@Query` property declarations across 2 view files** (the census's "7 sites" counts the historical/test-asserted and worktree copies; ground truth in `main` is 3):

| File | Line | Query |
|------|------|-------|
| `ResplitCore/Receipt List Container/ReceiptListView.swift` | 11 | `@Query(filter: #Predicate<Folder> { !$0.isArchived }, sort: \Folder.updatedAt, order: .reverse) var allTrips` |
| `ResplitCore/Receipt List Container/ReceiptListView.swift` | 19 | `@Query(sort: \Receipt.timestamp, order: .reverse) var allReceipts` |
| `ResplitCore/UI/FolderPickerView.swift` | 22 | `@Query(filter: #Predicate<Folder> { !$0.isArchived && $0.completedAt == nil }, sort: \Folder.name) var folders` |

Two of these (`allReceipts`, `allTrips`) back the **home receipt list**, which deliberately deleted its paginator and now relies on `List` + `@Query` for lazy infinite scroll AND for auto-refresh on CloudKit sync (see the load-bearing comment block at `ReceiptListView.swift:14-18`, and the regression test `ReceiptListInfiniteScrollRegressionTests.swift:33` that **asserts the exact `@Query` source string** — that test must be rewritten as part of this work, it is a pin we are intentionally moving). If our replacement drops a single live update — a scanned receipt that doesn't appear, a CloudKit import that doesn't repaint — the failure is invisible to unit tests and lands as a TestFlight "my receipt vanished" report. That is the blast radius. Per `groundtruth`, the live-update contract must be proven against a **real mutation + a real import-equivalent**, not a green compile.

### The SOOC contract: what views call instead of `@Query`

The Phase-1 spine is **Store-Owned Observable Collections (SOOC)**. The store owns identity + persistence and exposes **live, observable collections** that views read like any `@Observable` property. We do **not** invent a new query DSL in Phase 1 — each collection is a *named, pre-defined* live view that exactly mirrors one existing `@Query`'s predicate+sort. This keeps the migration mechanical (3 declarations → 3 named collections) with **no behavior change** and no new surface for an agent to over-engineer.

The contract is one protocol, `LiveCollection<Element>`, plus a store that vends the three concrete collections the app needs. A `LiveCollection` is:

- `@MainActor`-isolated and `@Observable` — reading `.elements` inside a SwiftUI `body` registers the view for invalidation exactly as `@Query` did. This is the *whole* substitution: `@Query var x: [T]` becomes `store.someCollection.elements`, both re-run `body` on change.
- **Identity-stable**: elements are keyed by `stableId` (the app-enforced identity from `UniqueIdentifiable.swift:10`, since CloudKit forbids SwiftData unique constraints — see `ResplitSchema.swift:30-32`). The collection guarantees `List` diffing sees stable identity across refreshes so scroll position and row animations survive a re-emit, which is the property the deleted paginator used to fight for.
- **Adapter-fed**: the *store* implementation is fixed; the *update source* is swapped per adapter (SwiftData today, in-memory for tests, SQLiteData/GRDB at the CKShare endgame). The view never sees the adapter.

```swift
import Foundation

/// A live, main-actor, observable collection of domain elements.
///
/// This is the contract a SwiftUI view subscribes to INSTEAD of `@Query`.
/// Reading `elements` inside a `body` registers the view for Observation
/// invalidation, so the view re-renders on every mutation the backing
/// adapter publishes — exactly the auto-refresh `@Query` gave us, including
/// CloudKit mirror imports.
@MainActor
public protocol LiveCollection<Element>: AnyObject, Observable {
  associatedtype Element: Identifiable & Sendable

  /// The current contents, already filtered + sorted per this collection's
  /// fixed spec. Reading this in a `body` subscribes the view to updates.
  /// Element order and `id` are stable across emits so `List` diffing keeps
  /// scroll position and row identity (the paginator-free infinite-scroll
  /// invariant the home list depends on).
  var elements: [Element] { get }

  /// True until the adapter has performed its first load. Lets a view show a
  /// skeleton instead of a false-empty on cold start (`@Query` returns `[]`
  /// before its first fetch — we preserve that but make the distinction
  /// available to callers that want it).
  var hasLoaded: Bool { get }
}

/// The Phase-1 store: owns the three named collections that replace the
/// three live `@Query` declarations. Vended from Factory, resolved at the
/// container root, injected via the SwiftUI environment.
@MainActor
public protocol ObservationStore: AnyObject {
  /// Backs `ReceiptListView.allReceipts` — `sort: \Receipt.timestamp, .reverse`.
  var receiptsFeed: any LiveCollection<ReceiptSnapshot> { get }
  /// Backs `ReceiptListView.allTrips` — active folders, `updatedAt` desc.
  var activeTrips: any LiveCollection<FolderSnapshot> { get }
  /// Backs `FolderPickerView.folders` — active + not-completed, by name.
  var pickableFolders: any LiveCollection<FolderSnapshot> { get }
}
```

**Element type decision (load-bearing):** `Element` is a **value-type snapshot** (`ReceiptSnapshot`, `FolderSnapshot`), *not* the live `@Model` object. This is the single most important contract choice and the bridge to the Records-and-Resolvers endgame:

- `@Query` handed views **live `PersistentModel` instances** — mutating `receipt.title` in a detail view wrote through. Our Phase-1 views are **read paths** (the list, the picker); they don't mutate the model object directly, they navigate to a detail view that resolves a fresh live model from the store by `stableId` and mutates *that* through `Database.transaction`. So returning snapshots costs us nothing at these 3 sites and buys us: `Sendable` elements (no live model crossing actor/thread boundaries — the exact hazard `Database.swift:5-8` and `DatabaseSnapshotReader` already guard against), trivial in-memory and GRDB adapters, and a read model identical in shape to the Records-and-Resolvers `Record` structs. The snapshot carries `id: String` (= `stableId`) so `List(selection:)` and navigation keep working. Where a call site genuinely needs the live model (e.g. `FolderPickerView` passing a `Folder` to `onFolderCreated`), the store exposes a `@MainActor func liveFolder(id:) -> Folder?` resolver that does a single `stableId` `FetchDescriptor` lookup — the same pattern `DatabaseModelResolver.folder` already implements.

### How each adapter emits live updates

The store is one class parameterized by a `LiveCollectionSource` per collection. The source is the only adapter-specific code; it owns "tell me when the data behind this spec changed, and give me the new snapshots." Three implementations:

**1. SwiftData adapter (today) — ModelContext + Observation, with CloudKit import coverage.**
This is the only adapter that must replicate `@Query`'s two trigger sources: (a) local saves on `mainContext`, and (b) CloudKit mirror imports. `@Query` got (b) for free because `NSPersistentCloudKitContainer` imports land in the same `mainContext` and SwiftData's query observation hooks the underlying Core Data change graph. We replicate both explicitly:

- **Local mutations:** observe `ModelContext.didSave` (the `NSManagedObjectContextDidSave`-equivalent SwiftData surfaces) on `Database.mainContext`. On notification, re-run the collection's `FetchDescriptor` (filter+sort+`propertiesToFetch: Receipt.listRenderProperties` — preserving the blob-skip that fixed Sentry RESPLIT-IOS-H8/H5, see `ReceiptsRepository.swift:153`) and map to snapshots.
- **CloudKit imports:** subscribe to `NSPersistentStoreRemoteChange` on the container's coordinator (the notification `NSPersistentCloudKitContainer` posts when the mirror writes). This is the trigger `@Query` consumed implicitly and the one most likely to be silently dropped — it gets its **own** named regression test driving a simulated remote-change post. `CloudKitManager.swift` already centralizes the sync-state surface (`.syncStatusDidChange`); we hang the import refresh off the same coordinator, not a re-implementation.
- **Coalescing:** both triggers funnel into one `@MainActor` debounce (a single `Task` cancel-and-replace, ~16ms) so a multi-row save or a burst import re-fetches once, not N times. Re-fetch is a `mainContext.fetch` (cheap, faulted, blob-skipped) → `map` → assign to the `@Observable` `elements`, which fires Observation invalidation.

**2. In-memory adapter (tests) — a subject.**
No SwiftData, no Core Data. The source holds `[Element]` and a continuation; mutations call `apply(_ mutate:)` which updates the array and assigns `elements`, firing Observation synchronously on the main actor. This is what `TestEnvironment.inMemoryContainer()` (`ReceiptSplitter/Mocks/TestEnvironment.swift`) graduates into for the 24 in-memory/`cloudKit: .none` configs — tests can `store.receiptsFeed` and assert reactivity **without** a `ModelContainer` at all, which removes the slowest part of those tests. Tests that *do* want to exercise the real SwiftData path keep `TestEnvironment.inMemoryContainer()` and use the SwiftData adapter against an in-memory store (its `didSave` path fires identically with `isStoredInMemoryOnly: true`). Both modes coexist.

**3. SQLiteData / GRDB adapter (CKShare endgame) — ValueObservation.**
The endgame read model is Records-and-Resolvers: plain `Record` structs + a `Filter`-enum query spec. GRDB's `ValueObservation` is the *native* live-collection primitive — it observes the SQL behind a request and emits a fresh value on every committing write, scheduled onto the main actor via `.start(in:scheduling: .async(onQueue: .main))` (or the structured `observe()` async sequence). The source wraps one `ValueObservation` per collection; the `Filter` enum compiles to the GRDB request. This is strictly *more* capable than `@Query` (it observes arbitrary SQL, joins included — needed for CKShare's shared-vs-private partition) and is the reason the SOOC `elements` contract is value-typed: GRDB hands back decoded `Record` values, which **are** our snapshots. The store and every view call site are byte-identical across the swap; only the source changes.

### @MainActor / threading contract

- The entire `LiveCollection` + `ObservationStore` surface is `@MainActor`. Views read `elements` from `body` (main actor); SwiftUI requires it; `@Query` was main-actor too. Non-negotiable and matches `Database.swift`'s "main-actor DB facade" stance (`Database.swift:4`, `mainContext` is `@MainActor`).
- **Adapters fetch off the hot path but publish on main.** The SwiftData adapter's re-fetch can run on the actor-owned `DatabaseSnapshotReader` (`Database.swift:61`) — which already exists precisely to keep heavy fetches off `mainContext` and **returns only `Sendable` snapshots** — then hop back to `@MainActor` to assign `elements`. This means a 2000-receipt re-fetch after a CloudKit burst doesn't jank the main thread; only the final `[Snapshot]` assignment touches the actor. The GRDB adapter gets this for free (ValueObservation fetches on a reader, schedules result on main). The in-memory adapter is trivially main-only.
- **No live model crosses a concurrency domain.** Because `Element` is `Sendable` snapshots and the store never vends live `PersistentModel`s through the collection, we structurally cannot reintroduce the cross-actor-live-model hazard the codebase already warns against (`Database.swift:5-8`). Live-model access stays funneled through the `@MainActor` `liveFolder(id:)`/`Database.transaction` resolvers.

### Performance contract

- **Lazy realization preserved.** The home list's whole point is `List` + `@Query` never materializing all rows. Snapshots are lightweight (the blob-skipped `listRenderProperties` set, `ReceiptsRepository.swift:153`), so even a full-corpus `elements` array is cheap value structs, not faulted blobs. `List` over `Identifiable` snapshots is still lazy at the cell level. We must **load-test the no-paginator path** (the deleted paginator existed to bound memory) — a corpus replay with N≈2000 receipts asserting steady-state memory + no main-thread fault realization. This is the perf regression most likely to bite and gets its own gate, mirroring the existing Corpus Tests discipline.
- **Coalesced re-fetch.** One debounced re-fetch per save-burst / import-burst, not per-row. A CloudKit initial sync that imports 500 records fires one `elements` reassignment, not 500.
- **Diffing stability.** `elements` are `Identifiable` by `stableId` and emitted in stable sort order, so SwiftUI's `List` diff is O(n) structural, not a full teardown — scroll position and row identity survive every re-emit. (This is the property the `ReceiptListInfiniteScrollRegressionTests` pin was protecting; the rewritten test asserts the *snapshot id stability* instead of the `@Query` source string.)

### View call-site sketch (mechanical, no behavior change)

```swift
// BEFORE — ReceiptListView.swift:19
@Query(sort: \Receipt.timestamp, order: .reverse)
private var allReceipts: [Receipt]

// AFTER — read the store-owned live collection from the environment.
@Environment(\.observationStore) private var store
private var allReceipts: [ReceiptSnapshot] { store.receiptsFeed.elements }
```

The `body` reads `allReceipts` exactly as before; Observation invalidates the view on every emit (local save OR CloudKit import) exactly as `@Query` did. The `List`, the month-grouping (`ReceiptListView.swift:534`), selection, and navigation all keep compiling against an `Identifiable` array — only the element type changes from `Receipt` to `ReceiptSnapshot` (carrying `id`, `title`, `timestamp`, `currencySymbol`, `totalAmount`, `ocrStatus` — whatever the row renders). The `selectedReceipt: Receipt?` binding becomes `selectedReceipt: ReceiptSnapshot?`, and the navigation destination resolves the live `Receipt` by `selected.id` via the store's `@MainActor` resolver before handing it to `FolderDetailView` — the single place a live model re-enters.

### Migration order + gates for this layer

1. Land `LiveCollection` + `ObservationStore` protocols + the SwiftData adapter + in-memory adapter (no view changes yet). Unit-test reactivity on both adapters: assert `elements` updates after a local insert **and** after a simulated `NSPersistentStoreRemoteChange` post.
2. Migrate `FolderPickerView.folders` first — lowest blast radius (a modal picker, not the home spine), proves the snapshot+resolver pattern end-to-end including the `liveFolder(id:)` path that `onFolderCreated` needs.
3. Migrate `ReceiptListView.allTrips`, then `allReceipts` last (highest risk). Rewrite `ReceiptListInfiniteScrollRegressionTests` to pin snapshot-id stability + live-update-on-import instead of the `@Query` source string.
4. **Visual proof gate is mandatory** (per repo §Visual Proof Merge Gate): the home list is a user-visible surface. BEFORE/AFTER screenshots of (a) scan a receipt → it appears at top, (b) the autobot CloudKit-import-equivalent → existing receipt updates. The "receipt vanished" failure mode is exactly what this gate exists to catch.

### Open risk flagged for Leo

`@Query`'s CloudKit-import auto-refresh is the one behavior we are **re-deriving rather than inheriting**. If the `NSPersistentStoreRemoteChange` subscription is mis-wired, the app looks perfect locally and silently stops updating on sync — invisible until a two-device test. The mitigation is the dedicated import-trigger regression test in step 1 + the two-device autobot visual gate in step 4; do not let this layer merge on green unit tests alone.

### Strangler-Fig Migration (incremental, never big-bang)

> Grounded on the real tree: `ResplitPersistence/API/Database.swift` (the
> `@MainActor` `DatabaseType` facade), `ReceiptSplitter/Models/*` (19 `@Model`),
> the 3 live `@Query` write sites (`ResplitCore/UI/FolderPickerView.swift:22`,
> `ResplitCore/Receipt List Container/ReceiptListView.swift:11` and `:19` — the
> other "@Query" hits in that folder are doc-comments, not code), and the
> existing test seam `TestEnvironment.inMemoryContainer()`. The strangler vine is
> the **`ResplitPersistenceContract`** module (Phase 1). SwiftData keeps running
> underneath the whole time; we route call sites through the contract one entity
> at a time and delete the SwiftData path only after each slice is green on both.

### Core principle: route, don't rewrite

The fig grows *around* the host before the host dies. Concretely: every step adds
a contract-routed path **next to** the existing SwiftData path, proves them
behaviorally identical via parallel-run, flips the call site, then deletes the old
path — never the reverse. At no commit is the app on a half-migrated entity. If a
step can't be made green on both paths, it reverts to one file, not a module.

**Hard rule (inherits PLAN authority line):** no step in this section introduces
SQLite/SQLiteData. The SwiftData adapter and in-memory adapter carry every step
below; the SQLiteData adapter is a compiling stub until Leo says go. Every step is
additive, worktree-isolated (per `bigapple` RESPLIT_DD_PATH), and collision-free
with the live product lane.

### Incremental sequence (entity dependency order — leaf-first)

Ordered by cascade/ownership coupling, lightest blast radius first. The census's
6 core models sort cleanly by relationship rule:

| Order | Entity | Why this position | Relationship facts (verified) |
|-------|--------|-------------------|-------------------------------|
| 1 | **Person** | True leaf. Owned by nobody; `.nullify` to participants. No cascade, no `@Query` view site, no CloudKit-share edge. The cheapest possible end-to-end proof. | `@Relationship(deleteRule: .nullify, inverse: \ReceiptParticipant.person)` — `Person.swift:24` |
| 2 | **Folder** | Near-leaf. `.nullify` to `Receipt` (deleting a folder orphans, never cascades). Has a real `@Query` write site → first observation-cutover rehearsal. | `@Relationship(deleteRule: .nullify, inverse: \Receipt.folder)` — `Folder.swift:23`; `@Query` at `FolderPickerView.swift:22`, `ReceiptListView.swift:11` |
| 3 | **SummaryItem** | Child value carried under a receipt; no inbound cascade-root duties. Migrate before its parent so the parent slice has a contract-routed child to lean on. | child of Receipt summary; no independent view query |
| 4 | **ReceiptItem** | Child line-item; split math reads it heavily (`ReceiptSplitCore`). Migrate after SummaryItem, before the root. | child of Receipt; consumed by split calculator |
| 5 | **ReceiptParticipant** | Join-ish entity between Receipt and Person; both its neighbors (Person, items) are already contract-routed by now. | inverse of `Person.participations` |
| 6 | **Receipt** | The cascade **root aggregate** — last on purpose. Owns the cascade delete, the live `@Query` at `ReceiptListView.swift:19`, OCR snapshot, FX conversion fields, and Live-Split merge fields (`liveMergeVersion`/`liveMergedAt`). By the time we get here, all 5 children already round-trip through the contract, so the root slice is "wire the aggregate," not "discover the model." | `@Model Receipt` (`Receipt.swift:17`), cascade root, ~30 persisted fields |

Rationale for leaf-first: a cascade-delete root migrated first would force us to
move all its children in the same commit (big-bang by the back door). Leaf-first
means each slice's children already speak the contract, so every step's diff is
bounded to one entity + its already-migrated neighbors.

### The FIRST vertical slice — Person, end-to-end through the contract

Person is the spike that proves the entire architecture with the least surface.
"End-to-end" = one entity travels create → read → observe → mutate → delete →
CloudKit-sync entirely through `ResplitPersistenceContract`, with SwiftData behind
the adapter, and the existing UI/tests see no behavior change.

1. **Define the contract surface for Person only** (in `ResplitPersistenceContract`):
   - A plain `PersonRecord` value struct (Records-and-Resolvers read model) — the
     fields off `Person.swift` (`uniqueId`, names, `cnContactId`, `ckUniqueID`,
     `phoneNumber`, `identityKey`, `cachedThumbnailData`), **no** SwiftData import.
   - A `PersonStore` protocol exposing the SOOC spine: an observable live
     collection (`var people: some Collection<PersonRecord>` published) plus
     `upsert`, `delete(id:)`, `find(identityKey:)`. This is the Phase-1 shippable
     façade; views/managers subscribe to the live collection.
   - A `PersonFilter` enum (the query spec) — `.all`, `.byIdentityKey(String)`,
     `.recentlyUsed` — so reads are declarative and adapter-portable.
2. **Wrap the existing facade in a SwiftData adapter** — `SwiftDataPersonStore`
   conforms to `PersonStore` by delegating to the current `Database` facade
   (`ResplitPersistence/API/Database.swift`): `upsert` → `mainContext.insert` +
   `saveIfNeeded()`, reads → `FetchDescriptor<Person>` mapped to `PersonRecord`,
   the live collection backed by a thin observer over the main context (the SOOC
   store owns identity, publishes records). The adapter is the ONLY file that
   imports both SwiftData and the contract — this is where the 180-file SwiftData
   coupling gets quarantined for Person.
3. **In-memory adapter in the same step** — `InMemoryPersonStore` (a dictionary +
   a published collection). This is what makes the slice testable with zero
   CloudKit and is reused by the Phase-0 characterization suite.
4. **Route ONE real call site through the contract** — pick the Person-write path
   in the contact/participant-resolution flow (the `ParticipantDisplayNameResolver`
   / person-matching path off `identityKey`), behind the `SwiftDataPersonStore`
   so prod behavior is byte-identical. Leave every other Person touch on direct
   SwiftData for now — that's the strangler boundary mid-slice.
5. **Parallel-run gate** (see next section) on that one path, then flip it.
6. **CloudKit proof** — the SwiftData adapter goes through the same
   `NSPersistentCloudKitContainer` (`ResplitCore/Persistence+CloudKit/CloudKitManager.swift`),
   so the slice inherits private sync unchanged; assert a Person upserted via the
   contract still round-trips through `cloudKit:.private` in a two-context test.

**Why Person and not Receipt:** Receipt is the root aggregate with cascade delete,
the live home-list `@Query`, OCR, FX, and Live-Split merge state — migrating it
first would drag 5 children + an observation cutover + CloudKit cascade semantics
into one commit. Person isolates the *architecture* question (does the
contract + SOOC + adapter triad hold?) from the *complexity* question (cascade,
observation, sync). Prove the triad on the cheapest entity; inherit it for the
expensive ones.

### Parallel-run vs SwiftData (the equivalence harness)

Each slice ships behind a temporary **dual-read assertion** before the old path is
deleted. This is the artifact that proves "no behavior change," not a vibe.

- **Shadow-read in DEBUG/test builds:** on every contract read for the migrating
  entity, also run the legacy SwiftData `FetchDescriptor` and `XCTAssert` the two
  result sets are equal (by `uniqueId` + field-by-field on the `Record`). Gated to
  DEBUG so prod ships one path; the assertion lives only long enough to flip the
  slice.
- **Dual-write reconciliation in tests:** characterization tests run the SAME
  mutation sequence against `SwiftDataPersonStore` (over `inMemoryContainer()`) and
  `InMemoryPersonStore`, then diff final state. This is the "same suite, every
  adapter" north-star story scoped to one entity.
- **Snapshot parity:** for the Folder/Receipt slices that touch `@Query` views, the
  10 existing snapshot tests + Autobot selectors run against the contract-routed UI
  and must be pixel-identical to the pre-slice baseline captured in Phase 0.
- **Tear-down rule:** the shadow-read assertion and the legacy `FetchDescriptor`
  for that entity are deleted **in the same PR that flips the call site** — leaving
  both paths live past the flip is exactly the fix-rot pattern `wiring-regression-lint.sh`
  exists to catch. After the flip, only the contract path remains for that entity.

### Per-step shippable / green gates

Every entity slice is its own shippable PR. A slice may NOT merge until ALL pass —
this maps onto the existing `CLAUDE.md` merge gate:

1. `tuist generate --no-open`
2. `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-claude-${SESSION_ID:-default}` (per §Build Isolation Mandatory)
3. `tuist test "ResplitCore Unit Tests"` + `tuist test "ReceiptSplitter Unit Tests"` — green
4. **Parallel-run equivalence test for THIS entity** — green on SwiftData adapter
   AND in-memory adapter (the dual-write diff is empty)
5. `tuist test "Resplit UI Tests"` + the 10 snapshot tests — identical to the
   Phase-0 baseline (mandatory once a slice touches a `@Query` view site)
6. `tools/lint/cloudkit-model-lint.sh` green — proves the slice didn't silently
   break CloudKit sync schema (the lint that the disabled CI used to enforce)
7. `tools/lint/wiring-regression-lint.sh` green — pin the contract entry symbols at
   their new call sites so a later refactor can't silently re-route to raw SwiftData
8. App still launches and the migrated flow works in the sim (Autobot walk for any
   entity with a view site) — visual proof per §Visual Proof Merge Gate when a
   user-visible surface (Folder picker, home list) is touched

**Slice-level invariant:** after each merge, `grep -rl "import SwiftData"` should be
**non-increasing**, and the count of direct `FetchDescriptor<ThatEntity>` /
`ModelContext` references for the just-migrated entity should drop to ~0 outside its
adapter. This is the strangler scoreboard — the 180/111/51 census numbers must
trend down per slice, never up.

### Which files move first (concrete first-three-PRs map)

**PR 1 — Contract module scaffold + Person slice (the spike):**
- *New:* `ResplitPersistenceContract/` module (Tuist target, depends on
  `ResplitFoundation` only — no SwiftData) containing `PersonRecord.swift`,
  `PersonStore.swift` (protocol + SOOC live collection), `PersonFilter.swift`.
- *New:* `ResplitPersistence/Adapters/SwiftData/SwiftDataPersonStore.swift` —
  conforms to the contract by delegating to the existing `Database` facade.
- *New:* `ResplitPersistence/Adapters/InMemory/InMemoryPersonStore.swift`.
- *Touch (one call site):* the person-matching/upsert path (resolver flow) is
  re-pointed at `PersonStore`; DI registration added next to
  `Container+Database.swift`.
- *Unchanged:* `ReceiptSplitter/Models/Person.swift` stays a `@Model` (it's the
  adapter's storage type) — we do NOT rip it out yet. The contract owns the value
  type; the `@Model` is demoted to an adapter implementation detail.

**PR 2 — Folder slice + first observation rehearsal:**
- *New:* `FolderRecord`, `FolderStore`, `FolderFilter` in the contract module;
  `SwiftData`/`InMemory` Folder adapters in `ResplitPersistence/Adapters/`.
- *Touch:* `ResplitCore/UI/FolderPickerView.swift:22` — replace the `@Query(filter:
  #Predicate<Folder>{ !$0.isArchived && $0.completedAt == nil })` with a
  subscription to `FolderStore`'s live collection filtered by `.activeUnarchived`.
  This is the first of the 7 view sites to leave `@Query`, and Folder's `.nullify`
  edge makes it the safest one to rehearse on.

**PR 3+ — children, then the root, in dependency order:** SummaryItem → ReceiptItem
→ ReceiptParticipant adapters land as their own PRs (no view sites, so they're
pure store-layer slices). `ReceiptListView.swift:11` (Folder `@Query`) flips with
PR 2's Folder work; `ReceiptListView.swift:19` (Receipt `@Query`) flips only in the
**final** Receipt-root slice, once all children speak the contract, the cascade
delete is reimplemented through `ReceiptStore`, and the home-list snapshot parity is
green. `ResplitSchema.swift` (the `Schema`/`VersionedSchema` registry) is touched
**last and minimally** — it stays the SwiftData adapter's schema definition; we do
not migrate the schema file itself, we migrate the call sites that read through it.

**Never-move-first list:** `ResplitSchema.swift`, `CloudKitManager.swift`, and the
`Database` facade body are migration *substrate*, not migration *targets* — they're
the host trunk the vine climbs. They change only when the last entity (Receipt) is
routed and the SwiftData adapter is the sole remaining SwiftData importer.

### Pre-Mortem Guardrail Table

> **Why this section exists.** A prior weaker-model attempt to rip everything out of SwiftData into an in-memory store **FAILED**: it went big-bang, tried to sever all 180 SwiftData imports / 19 `@Model` types / 111 `ModelContainer` refs at once, and ran out of budget mid-flight — leaving a half-cut tree that neither built nor reverted cleanly. This plan's entire shape (Phase-0 safety-net-first, contract module with **no** behavior change, one-entity vertical slice, SOOC keeping `@Query`/`ModelContext` in the 7 view sites untouched until Phase 4, SQLiteData stubbed until Leo says go) is a direct counter to that failure. The table below names the **specific** way this codebase kills a naive port and pins each one to a concrete guardrail already in the phase map / queue — not generic advice.
>
> Ground-truth anchors (verified 2026-06-13, real paths): prod container at `ResplitCore/AppBootstrapView.swift:52` builds `ModelContainer(for: ResplitSchema.versioned, migrationPlan:)` with **no** `cloudKitDatabase:` argument; facade at `ResplitPersistence/API/Database.swift` is `@MainActor`-pinned with `DatabaseSnapshotReader` as the only sanctioned off-main path; schema anchor `ResplitSchemaV1` (`versionIdentifier 1.0.0`) in `ReceiptSplitter/Models/ResplitSchema.swift`; lazy feed `@Query(sort: \Receipt.timestamp, order: .reverse)` at `ResplitCore/Receipt List Container/ReceiptListView.swift:19`; cascade root `Receipt.swift:82,99,102` (3× `.cascade`).

### A. The scope-blowup failure that already killed one attempt

| # | Failure mode (codebase-specific) | What it looks like when it bites | Guardrail in THIS plan |
|---|----------------------------------|----------------------------------|------------------------|
| **S1** | **Big-bang severance.** 180 files `import SwiftData`, 111 `ModelContainer` refs, 51 `ModelContext` refs, 19 `@Model` types. Trying to convert them in one pass is exactly what burned the prior attempt's budget with a non-building, non-revertable tree. | Hundreds of compile errors at once; no green checkpoint to fall back to; budget exhausted with zero shippable increment. | **Strangler-fig, not rewrite.** Phase 1 adds a *new* `ResplitPersistenceContract` module **alongside** SwiftData with **zero** call-site changes (Checkpoint 1: "app still on SwiftData, suite green"). Phase 2 converts **exactly one entity** end-to-end and **parallel-runs** it against direct SwiftData (Checkpoint 2: "slice green on both paths"). The 7 `@Query` view sites are not touched until **Phase 4**. Every queue row has **disjoint write scope** + its own green checkpoint, so the tree is always revertable to the last checkpoint. |
| **S2** | **15 load-bearing blockers treated as uniform.** The census found 15 blockers but they are not equal weight — `@Query` laziness, the cascade graph, the implicit CloudKit bind, and `@MainActor` pinning each fail differently. A weaker model flattens them and cuts the dangerous ones first. | The cheap blockers get severed, the load-bearing ones (CloudKit, cascade, lazy-fetch) silently regress because they have no compile error to announce themselves. | **SOOC keeps the dangerous edges intact by construction.** The store keeps owning identity/persistence and *publishes* live collections; `@Query` and `ModelContext` semantics are preserved behind the observation API, so the high-risk blockers (B1–B6 below) are **deferred to dedicated phases with their own checkpoint**, not swept in pass one. Full value-type domain is explicitly **post-launch**. |
| **S3** | **Endgame creep.** Reaching for SQLiteData / CKShare immediately (the real prize) pulls an unproven third-party dependency into the critical path before the contract is even stable. | The port can't ship because it's blocked on a CKShare/SQLiteData spike; Phase-1 value never lands. | **SQLiteData adapter is a STUB until Leo says go** (PLAN authority line 3-6). Phase-1 shippable spine is SOOC on the **SwiftData** adapter. SQLiteData is Phase 3/5, contained by (a) the adapter boundary and (b) a fork + upstream-tracking patch branch. Records-and-Resolvers is adopted only as the *read model* for that endgame, not the Phase-1 deliverable. |

### B. The six codebase-specific landmines (one per named risk)

| # | Failure mode | The exact mechanism in Resplit | Guardrail in THIS plan |
|---|--------------|--------------------------------|------------------------|
| **B1 — `@Query` view coupling → lazy-fetch + blob-fault regression** | A naive in-memory store hands views a plain array instead of SwiftData's lazy `@Query`. | `ReceiptListView.swift:19` is `@Query(sort: \Receipt.timestamp, order: .reverse)` feeding a `List` with **no paginator** — laziness is structural. `Receipt.listRenderProperties` exists *specifically* so a bulk fetch never realizes the `@Attribute(.externalStorage)` JPEG (200KB–2MB) on the main thread. This is the documented root cause of Sentry **RESPLIT-IOS-H8/H5** (`Receipt.currencyCode.getter` hangs, 2.5–4.9s). A swap that materializes all receipts eagerly resurrects that hang. | **`@Query` is not replaced until Phase 4**, and only with the contract's observation API that preserves the same lazy/partial-fetch contract. SOOC's published collections must honor `listRenderProperties` partial realization. **Checkpoint 4 = "UI snapshots identical."** Phase-0 must add a characterization/perf assertion that the receipt-list path does **not** fault `receiptImageData` (guards H8/H5 by construction, satisfying MT-5 on the revert-prone list surface). |
| **B2 — Receipt cascade graph → orphaned children on delete** | The new store must reproduce SwiftData's `.cascade` delete semantics exactly. | `Receipt.swift` is the root aggregate with **three** `@Relationship(deleteRule: .cascade)` edges — `participants` (82), `items` (99), `summaryItems` (102) — plus a **non-cascade** `folder` (86) that must survive a receipt delete. The inverse keypaths (`\ReceiptParticipant.receipt`, etc.) are wired both ways. An adapter that drops a Receipt but leaves children, or that cascades into `folder`, corrupts data and CloudKit. | Cascade behavior is in the **North-Star test stories** ("Receipt-cascade behavior identical across adapters") and is a **Phase-3 adapter conformance gate** ("run the Phase-0 suite against each adapter"). Phase-0 must add a characterization test asserting: delete Receipt → participants/items/summaryItems gone, **folder still exists**. That test runs green ×3 adapters at Checkpoint 3 before any adapter is trusted. |
| **B3 — ModelContext threading / `@MainActor` → cross-actor live-model crash** | A new store that passes live model objects across concurrency domains breaks SwiftData's main-actor contract. | The facade `Database` (`ResplitPersistence/API/Database.swift`) pins **every** mutating op to `@MainActor`; the *only* sanctioned off-main path is `DatabaseSnapshotReader` (an `actor`) which **returns Sendable snapshots, never live models** (its own doc comment says so). `Receipt.stableId` falls back to `ObjectIdentifier(self)` — instance-pointer identity that is meaningless across contexts. A weaker model "moves work off-main" by sharing live models and hits non-deterministic crashes the test suite won't reliably reproduce. | The contract API is designed **Sendable-first**: reads return value snapshots / `Record` structs (the Records-and-Resolvers read model), writes go through the `@MainActor` facade or a `ModelActor`-style boundary — never a shared live `ModelContext`. Phase-1 contract types must be `Sendable`; the in-memory adapter must enforce the **same** main-actor write discipline so a green in-memory test can't hide a threading bug that only fires on the SwiftData/CloudKit adapter. (Pairs with the repo's `swift-concurrency` ModelActor guidance.) |
| **B4 — `NSPersistentCloudKitContainer` binding → silently severed private sync** | The CloudKit bind is **implicit** — there is no `.private` flag to grep for. | Prod container (`AppBootstrapView.swift:52-55`) is `ModelContainer(for: ResplitSchema.versioned, migrationPlan:)` with **no `cloudKitDatabase:` argument** → SwiftData auto-binds `NSPersistentCloudKitContainer` private DB from the entitlement. `CloudKitManager.swift` subscribes to `NSPersistentCloudKitContainer.eventChangedNotification` for sync state. Rip SwiftData out and sync dies **with no compile error and no test failure** — exactly the kind of green-but-broken regression the prior attempt couldn't see. There is already an existing `tools/lint/cloudkit-model-lint.sh` guarding model-level CloudKit breakage. | CloudKit sync is **kept on the SwiftData adapter for Phase-1 ship** — SOOC does not touch the container's CloudKit bind. The contract must **not** force `cloudKitDatabase: .none` on the production path. Native CKShare on SQLiteData is **Phase 5 only**, behind a **two-device share/accept/edit story that must be green** (Checkpoint 5) before it replaces the working `NSPersistentCloudKitContainer` path. Phase-0 must inventory the CloudKit-event path as a coverage gap (it's a real-account path the 24 `cloudKit:.none` test configs deliberately don't exercise). |
| **B5 — SwiftData implicit identity / change-tracking → broken `@Query` updates + sync diffs** | Views auto-refresh because SwiftData change-tracking notifies `@Query`; CloudKit syncs because it tracks dirty objects. A custom store must reproduce **both**. | `@Query` "auto-updates on CloudKit sync" (per `ReceiptListView.swift:18` comment) — that update is change-tracking-driven. Identity is `uniqueId`-or-`ObjectIdentifier` via `stableId` (`UniqueIdentifiable.swift`), used for `ForEach`/selection. `Receipt.hash` combines `stableId`. An adapter with a different identity/dirty-tracking model makes lists not refresh, selection jump, or CloudKit push the wrong delta. | SOOC makes the **store** own identity + change publication, so the observation API emits updates on the **same** identity contract (`stableId`/`uniqueId`) regardless of adapter — that's the whole point of the chosen design. Records carry the stable `uniqueId`, not pointer identity. Phase-2 vertical slice **parallel-runs** the new path vs direct SwiftData and asserts the published collection updates match SwiftData's `@Query` updates 1:1; snapshots must be **identical** (Checkpoint 2). |
| **B6 — Schema identity drift → orphaned on-disk + CloudKit store** | A new backend that doesn't reproduce the **exact** store identity can't open the existing user's database — every shipped user loses their receipts. | `ResplitSchema.swift` makes `ResplitSchemaV1` (`versionIdentifier = Schema.Version(1,0,0)`) the **byte-identical** store anchor; all `ModelContainer`/`Schema` construction is mandated through `ResplitSchema.versioned` + `ResplitSchema.migrationPlan` (`ResplitMigrationPlan`). The file's own comment warns the V1 anchor "is what gives" a stable store and "do NOT change this enum's model shapes." A naive port that re-derives the schema (or omits the migration plan) mints a *new* store identity and orphans every existing record locally and in CloudKit. | The SwiftData adapter **must** keep constructing through `ResplitSchema.versioned` + `migrationPlan` unchanged — the contract wraps it, never replaces it. The SQLiteData/CKShare endgame is gated on a **migration story** (Phase 5) that reads the existing `ResplitSchemaV1` store, not a fresh one. Phase-0's "migration" coverage section + the strangler-fig steps must prove an existing on-disk store still opens after each phase. **No persistence file moves until Phase-0's safety net is green** (phase-map invariant). |

### C. Cross-cutting guardrails that catch "green but broken"

| Guardrail | What it defends against | Where it lives in the plan |
|-----------|-------------------------|----------------------------|
| **Test the real dependency, not a mock of it.** | The prior failure mode this whole org has hit before: a fully-green session that was fraudulent because the external dependency (CloudKit/voice) was mocked out. The 24 `cloudKit:.none` / in-memory configs make it trivially easy to "prove" the port works while real CloudKit sync is dead (B4). | North-Star story "**Two-iCloud-account CKShare share/accept/edit** on the SQLiteData adapter" forces a **real two-device** test, not a `cloudKit:.none` stub. Phase-0 explicitly inventories CloudKit + Live Split as coverage gaps the in-memory configs don't cover. |
| **Adapter parity is the gate, not adapter green.** | An in-memory adapter passing alone proves nothing about SwiftData/CloudKit behavior (threading B3, cascade B2, change-tracking B5 all differ). | "**Same regression suite, green against SwiftData adapter AND SQLiteData adapter**" + Checkpoint 3 "suite green ×3 adapters." A story that only passes on one adapter is a **fail**, per the North-Star pass/fail criteria. |
| **Every checkpoint is revertable.** | Budget exhaustion mid-cut (the original failure) leaving a non-building tree. | Phase map: each phase ends at a checkpoint "**green before the next begins**," app stays on SwiftData through Phase 3, disjoint write scope per queue row. There is always a last-green-checkpoint to fall back to — a budget run-out costs the *current* phase, never the whole port. |
| **MT-5 regression tests on revert-prone surfaces.** | The receipt list (B1), Live Split, and CloudKit are exactly the UI/Live-Split/FX surfaces the repo's revert-cluster rule covers; a perf/sync regression here is invisible to a smoke test. | Phase-0 characterization tests + golden snapshots double as the MT-5 contrapositive assertions (no-blob-fault on list, cascade-not-into-folder, sync-event path). Bundled in the same slice as the change, never two-stepped. |

### Risk Register

Grounded in the live resplit-ios surface (180 SwiftData imports, 19 `@Model`, 7 `@Query` sites, 111 `ModelContainer` / 51 `ModelContext` refs, 15 load-bearing blockers, 337 XCTest / 74 Autobot / 10 snapshot / 24 isolated configs) and the CKShare/SQLiteData decision (`resplit-ckshare-sqlitedata-decision`). Likelihood/Impact: L/M/H. **Severity** = the row's standing in the launch window. Rows R1–R6 are the prompt's named must-cover risks; R7–R12 are the adjacent blast-radius risks the census surfaced.

| # | Risk | Likelihood | Impact | Mitigation (concrete, grounded) |
|---|------|:---:|:---:|------|
| **R1** | **15 load-bearing blockers don't fully sever.** The facade `DatabaseType` (`ResplitPersistence/API/Database.swift`) is itself leaky — its public protocol exposes `ModelContainer`, `@MainActor mainContext: ModelContext`, `fetch<T: PersistentModel>(FetchDescriptor<T>)`, `transaction((ModelContext) -> Void)`. Any blocker that re-exports a SwiftData type through the "contract" re-couples the whole graph; a swap then reverts to the 180-file rewrite the module boundary exists to avoid. | H | H | Treat the 15 blockers as a checklist with a per-blocker severed/test in Phase 1, not a count. **Build-fence test:** the contract module must compile with `import SwiftData` BANNED (grep gate in CI: `! grep -rl 'import SwiftData' ResplitPersistenceContract`). Records-and-Resolvers `Record` structs + `Filter` enum are the ONLY types crossing the boundary — no `PersistentModel`, `ModelContext`, `FetchDescriptor`, `ModelContainer` in any public signature. Phase-2 vertical slice proves one entity round-trips through plain values before the other 18 follow. Each blocker severed = one adversarial red-team row that tries to reach SwiftData through the new seam. |
| **R2** | **Observation cutover (`@Query` → contract API) breaks the 7 view sites** — the exact piece that killed the prior big-bang attempt. SwiftData `@Query` carries implicit auto-update, animation, sort/predicate, and main-actor diffing semantics; a hand-rolled `@Observable` collection that's even subtly off (stale snapshot, missed insert, wrong sort, lost animation) ships a silent data-correctness or UX regression into live receipts. | H | H | SOOC (Store-Owned Observable Collections) keeps the store owning identity/persistence and publishing live collections, so the 7 sites see NO behavior change by design. Gate the cutover on the 10 snapshot tests + 74 Autobot UI selectors being **byte-identical before/after** (Checkpoint 4). Do the 7 sites **one at a time** behind the contract with parallel-run (old `@Query` and new observable rendered into a diff harness) until snapshots match, then delete the `@Query`. No site flips without its golden snapshot green. Characterization tests for auto-update/sort/animation added in Phase 0 BEFORE the first site moves. |
| **R3** | **CloudKit / CKShare correctness — dropped edits on a shared receipt.** `CloudKitManager.swift` already wires `NSPersistentCloudKitContainer` private sync (imports CoreData). The CKShare endgame on SQLiteData inherits its open data-loss bugs that hit Resplit's EXACT case: #418 (delete + same-UUID re-insert loses data — Receipt is a cascade-delete root with 5 relationships), #356/#354 (conflict resolution diverging from last-edit-wins). Two people editing one receipt → a silently dropped edit is the failure that matters, and simulators have no CloudKit push so it's invisible in the normal suite. | H | H | **Two-device, two-iCloud-account real-share smoke is a HARD gate** for any CKShare claim (simulators can't prove it — per `test-real-flows-not-green-checks`). Build an adversarial data-loss harness targeting #418/#356/#354: delete→same-UUID re-insert, concurrent two-side edits, conflict→last-edit-wins assertion. Add the **test-enforced CloudKit model-invariant contract NOW** (zero-regret, keeps SQLiteData AND Core Data doors open; today the optional/`.none` invariant is hand-reviewed, not test-enforced). Hand-write CKShare participant/share verification (Apple's 2021 un-share bug is still unfixed → you write it either way). CKShare stays Phase 5, post-launch, displacing nothing on the ASC/Sentry P0 list. |
| **R4** | **SQLiteData (Point-Free) dependency — death, breaking change, or macro lock-in.** Third-party SwiftPM dep with a macro DSL; an upstream break, abandonment, or API churn could strand the migration mid-flight. | L | M | Dependency fear is **manageable, not the real risk** (the sync-correctness in R3 is). Containment: (a) the adapter boundary makes it a one-module swap, not a 180-file rewrite; (b) fork + upstream remote + rebased patch branch, SwiftPM pinned to the fork; (c) MIT-licensed + heavily maintained; (d) on-disk data is **plain portable SQLite** — worst case rip out the macros, drop to raw GRDB, migrate **zero data**. Keep the macro DSL behind a thin data-access layer so a fork stays contained. **This whole dep is GATED on Leo** — the adapter is a stub until then; planning/prework proceeds with SQLiteData NOT in the build, so this risk is currently dormant by policy. |
| **R5** | **Migration data-loss** — corrupting or dropping live user receipts during the SwiftData→(eventual) SQLiteData move. `ResplitSchemaV1` exists but has **no `ResplitSchemaV2` / no custom `MigrationStage` yet** — the store rides Apple lightweight (inferred) migration only. A schema move that isn't byte-identical, or a cutover without a verified backup, risks irreversible loss of real user data on devices already syncing via CloudKit. | M | H | **No persistence file moves until Phase 0's safety net is green** (hard PLAN rule). Strangler-fig, never big-bang: first vertical slice + parallel-run + per-step shippable/green gates. Wrapping current live models in `ResplitSchemaV1` is **byte-identical** (already done — the safe anchor). Any schema change adds `ResplitSchemaV2` + an explicit `MigrationStage`, never an implicit inference jump. Pre-migration: golden export of a real seeded store + round-trip restore assertion. SQLite portability (R4) means the eventual cross-engine move is a data copy with a verifiable row/aggregate count diff, not a destructive transform. Migration is a SEPARATE goal Leo launches deliberately — not in this planning/prework runway. |
| **R6** | **Parallel-lane collision** — product dev is live in a parallel chat/lane on resplit-ios; non-additive prework editing hot files (or a `killall xcodebuild`/sim) corrupts the other lane's WIP or build. | M | M | Mandatory isolation: all prework in a git **worktree** off resplit-ios, prefer NEW additive files, never edit hot files the other lane touches, never `killall xcodebuild`/sims (per `/bigapple` swarm safety + per-lane `RESPLIT_DD_PATH` DerivedData). If a change isn't additive + collision-free, **it stays a PLAN row, not a commit.** Honor existing collision guards before mutating shared state. |
| **R7** | **Phase-0 safety net is green-washed, not real** — characterization tests that pass by asserting their own mocks/snapshots rather than current behavior, so the baseline they "lock" is fiction and a later regression slips through clean. | M | H | Apply `/groundtruth`: a test must exercise the REAL current path (real `ModelContext`, real fetch, real diff), not a tautology. Snapshot inventory must cover the actual 7 `@Query` sites + 6 core models + Live Split + CloudKit invariant. Coverage map signed off at Checkpoint 0 with each gap → a named test to add (P0.2). Adversarial pass tries to BREAK each characterization test before it's trusted. |
| **R8** | **In-memory adapter parity drift** — the in-memory adapter (tests) diverges from SwiftData semantics (cascade delete on Receipt's 5 relationships, sort stability, uniqueness), so the same suite passes in-memory but the SwiftData/SQLiteData adapters behave differently in prod. | M | M | One suite, three adapters (Checkpoint 3: green ×3). The 24 isolated configs (206 in-memory/`cloudKit:.none` sites) become the shared adapter-conformance harness. Cascade-delete, sort, and uniqueness are explicit conformance tests every adapter must pass identically — a divergence is a red bar, not a per-adapter `#if`. |
| **R9** | **Live Split (websocket real-time session) behavior changes under the new store.** Live Split is a real-time session feature; if the store's observation/commit timing shifts, in-flight session state or settle math can diverge across participants. | M | M | Live Split is a named North-Star story tested identically across adapters (PLAN seed: "Live Split + Folder + Receipt-cascade behavior identical across adapters"). Add a characterization test for the websocket→store commit path in Phase 0 before any store wiring changes; gate the cutover on it staying green. |
| **R10** | **Scope creep — planning/prework drifts into shipping the SQLiteData migration or polish** during the Resplit 2.0 launch window, displacing P0 ASC/Sentry bugs. | M | M | Hard policy: introducing SQLiteData + disruptive migration is a SEPARATE goal Leo launches deliberately; the adapter stays a stub. This planning goal is agent-checkable and **exits on refire** when done-state is met — it does not loop into execution. Per §Scope Discipline: P0 = user-reported bugs win over any persistence-refactor row during the launch window. |
| **R11** | **Composition-root / DI wiring regression** — 111 `ModelContainer` + 51 `ModelContext` refs mean the app boots its store in many places; rewiring one adapter through a single composition root can miss a call site and ship two stores or a wrong-adapter boot. | M | M | One composition root wires exactly one adapter (Tuist module graph artifact); audit all 111 `ModelContainer` refs into "owned by root" vs "leaked" buckets in Phase 1 — leaked refs are blocker rows. App stays on SwiftData through Phases 1–4 (Checkpoint 1: builds, app still on SwiftData, suite green) so the wiring change is observable in isolation. |
| **R12** | **Tuist module-graph cycle / build-time regression** — adding the contract + adapter modules introduces a dependency cycle or balloons clean/incremental build time, slowing the live product lane. | L | M | `/tuist` best-practices: contract module depends on nothing app-specific; adapters depend on contract, never the reverse; composition root is the only place that sees a concrete adapter. Verify the graph is acyclic with `tuist graph` and confirm binary-cache hit rate before/after. Module split is additive (new targets), so the existing lane's build path is unchanged until it opts in. |

**Top-3 launch-window watch (severity-ranked):** R3 (CKShare dropped-edit — needs real two-device proof, post-launch) · R2 (observation cutover — the prior-attempt killer) · R1 (blockers don't fully sever — re-couples the graph). R4 (dependency death) is the *named fear that is actually contained*; the register's load-bearing risks are correctness (R2/R3) and data-loss (R5), not the dependency.

---

## CKShare / SQLiteData Fit + Fork Strategy

> Grounded against `pointfreeco/sqlite-data` @ `main` (latest tag **1.6.6**,
> default branch `main`, 27 open issues) on 2026-06-13. API names, the
> root-record constraint, and the three bug numbers are verified against live
> source + the GitHub issues API, not memory. This section is the Phase-5 spec.

### Why SQLiteData for the CKShare endgame (vs staying on NSPersistentCloudKitContainer)

Resplit ships **`NSPersistentCloudKitContainer` private sync today**
(`ResplitCore/Persistence+CloudKit/CloudKitManager.swift`). NSPCKC gives private
mirroring for free but its **shared-database / CKShare story is the weak part**:
`UICloudSharingController` + `share(_:to:)` wiring on top of NSPCKC is famously
finicky (the shared store needs its own container config, accepted shares land in
a separate persistent store, and conflict/permission surfacing is opaque).
SQLiteData was built **CloudKit-sharing-first** and exposes a small, typed API
over the same primitives — so the endgame share/accept/permission flow is a
library call, not a hand-rolled CloudKit dance.

Critically, SQLiteData's sharing is **backend-free and rides iCloud identity**:
there is no Resplit-owned server in the share path. A `CKShare` is created in the
user's **private** CloudKit database, the invitee accepts via a system share link
(iMessage/email), and CloudKit places the shared record set in the invitee's
**shared** database. Identity, invitation, and access control are all Apple's —
Resplit never sees a participant's Apple ID, runs no relay, and stores no share
state outside CloudKit. This is the same trust model as today's private sync,
extended to multi-user, with **zero new backend** (distinct from Live Split,
which is our own websocket session and stays our own).

### How CKShare binds in the SQLiteData adapter

The adapter does NOT expose `CKShare` to `ResplitCore`/`ResplitUI` — sharing is a
**capability of the SQLiteData adapter only**, declared on the persistence
contract as an optional `SharingCapability` that the SwiftData and in-memory
adapters return `nil`/unsupported for. Concretely:

1. **Create a share.** SQLiteData provides `SyncEngine.share(record:configure:)`
   on `SyncEngine`, returning a `SharedRecord`. The `configure` closure sets
   `CKShare` system fields (e.g. `share[CKShare.SystemFieldKey.title]`). The
   returned `SharedRecord` drives a `CloudSharingView` sheet (the library's
   wrapper around `UICloudSharingController`). Our adapter wraps this as
   `share(receipt:) async throws -> ResplitSharedRecord` and keeps `CKShare` /
   `SharedRecord` behind the contract type so `ResplitUI` presents a
   `CloudSharingView` it gets from the adapter, never importing CloudKit.
2. **Accept a share.** SQLiteData provides `SyncEngine.acceptShare(metadata:)`.
   The app's `UIWindowSceneDelegate` implements
   `windowScene(_:userDidAcceptCloudKitShareWith:)` **and** the
   `connectionOptions.cloudKitShareMetadata` cold-launch path, forwarding the
   `CKShare.Metadata` to the adapter's `acceptShare(metadata:)`. This is the one
   place CloudKit types touch app code — it lives in the `ReceiptSplitter` app
   target's scene delegate, not in a domain module.
3. **Permissions.** SQLiteData auto-enforces read-only vs read-write: a write to
   a record the user lacks permission for throws `DatabaseError` whose `.message`
   equals `SyncEngine.writePermissionError`. To gate UI ahead of the error, the
   adapter joins the root table to `SyncMetadata` and reads
   `SyncMetadata.share` → `share.currentUserParticipant?.permission == .readWrite`
   (or `publicPermission`). Our contract surfaces this as a coarse
   `SharePermission { .readOnly, .readWrite, .none }` so `ResplitUI` can disable
   edit affordances without touching CloudKit.
4. **Setup requirements.** Add `CKSharingSupported = true` to the app
   `Info.plist` (subtle but mandatory per Apple's sharing docs) alongside the
   existing CloudKit container + entitlements. No new container needed — sharing
   uses the existing private/shared databases of the same iCloud container.

### The root-record constraint is the schema-design landmine for Resplit

SQLiteData enforces: **only "root" records (no foreign keys) can be shared.** An
association is shareable only if it has **exactly one** foreign key pointing at a
record that itself satisfies the rule, applied recursively. Sharing a non-root
record **throws**.

Map onto Resplit's 6 core models:

| Model | Role | FKs | Shareable as root? |
|-------|------|-----|--------------------|
| **Receipt** | root aggregate, cascade delete | none (is the parent) | **YES — this is THE share root** |
| ReceiptParticipant | child of Receipt | → Receipt | no (shared transitively via Receipt) |
| ReceiptItem | child of Receipt | → Receipt | no (transitive) |
| SummaryItem | child of Receipt | → Receipt | no (transitive) |
| Person | reusable across receipts | (none, but referenced) | **DANGER — see below** |
| Folder | groups receipts | (none, but Receipt → Folder) | not a share unit |

**The trap:** Resplit's natural model has `ReceiptParticipant`/`SummaryItem`
referencing a shared **`Person`** (a person reused across many receipts). If
`ReceiptParticipant` has **two** FKs (→ `Receipt` AND → `Person`), it **violates
the single-FK rule and cannot be shared** — and `Receipt` then can't be shared
either if its children don't satisfy the recursive rule. This is the #1 schema
decision Phase-5 must settle: when sharing a Receipt, participants likely need to
be **denormalized/snapshotted onto the Receipt's owned subtree** (participant
name/amount copied per-receipt, no cross-receipt `Person` FK in the shared
subtree), with the `Person` library staying device-local/private. This is
exactly the refactor pattern in bug **#418** below — collapsing an asset to a
combined PK/FK into its parent — so it must be designed, then guarded by a test,
not discovered in prod. **Acceptance:** Phase-5 produces a shareable-subtree
schema where `Receipt` is a valid root and every shared child has exactly one FK
back toward the root, with a test asserting `share(receipt:)` does NOT throw.

### Fork-tracking strategy for the SQLiteData dependency

SQLiteData is pre-1.0-maturity for sharing (27 open issues, active conflict-
resolution churn). We do NOT depend on a moving `main`, and we keep the ability
to carry local patches without waiting on upstream merges. Strategy:

1. **Fork** `pointfreeco/sqlite-data` → `firstbitelabs/sqlite-data` (or
   `leojkwan/sqlite-data`).
2. **Remotes on the fork clone:** `origin` = our fork, `upstream` =
   `pointfreeco/sqlite-data`. Never commit to `main` on the fork — keep `main`
   a clean mirror of upstream so diffs stay legible.
3. **Patch branch** `resplit-patches` **rebased on top of upstream tags**, never
   merged. Each local fix is one focused commit with a `# UPSTREAM: <issue/PR>`
   trailer so we know when a commit can be dropped (upstream landed it). Tag our
   builds as `<upstream-tag>+resplit.N` (e.g. `1.6.6+resplit.1`).
4. **SwiftPM pins to the fork by exact revision/tag**, not a branch:
   ```swift
   .package(
     url: "https://github.com/firstbitelabs/sqlite-data.git",
     exact: "1.6.6-resplit.1"   // immutable tag on resplit-patches, NOT .branch
   )
   ```
   Pinning to a tag (or `.revision("<sha>")`) makes builds reproducible and
   stops a silent upstream `main` shift from changing our sync semantics. In
   Tuist, the dependency is declared in `Package.swift` / `Tuist/Package.swift`
   and the SQLiteData adapter module is the **only** module that links it — the
   contract module and `ResplitUI` do not, so a fork bump is a one-module
   rebuild.
5. **Automate the drift rebase.** A scheduled job (LaunchAgent or CI, on the
   default 30-min/weekly cron cadence — weekly is right for a dependency) runs:
   `git fetch upstream --tags`, attempt `git rebase upstream/main` (or the newest
   tag) onto `resplit-patches`, run SQLiteData's own test suite **plus** our
   adapter conformance suite against the rebased fork, and open a PR
   `chore: rebase resplit-patches on <new-upstream-tag>` on **green**. On rebase
   conflict or red tests it opens a draft PR with the failure and **stops** —
   never force-pushes the patch branch unattended (that's a Hard-NEVER). Drift
   stays small because rebases are frequent and each is gated by the same
   suite that protects the app.
6. **Drop-on-upstream.** When `git log upstream/main` shows our `# UPSTREAM:`
   issue closed, drop that patch commit on the next rebase. The fork shrinks
   toward zero local delta as upstream catches up; if it ever hits zero we can
   re-pin straight at `pointfreeco/sqlite-data` and retire the fork.

### Known sync-correctness bugs to guard (verified live, all OPEN, label `bug`)

These are upstream issues we MUST have characterization/regression tests for
**before** trusting SQLiteData with real receipts. They are the patch-branch
candidates and the highest-value Phase-5 test stories.

- **#418 — CloudKit data loss: delete-then-reinsert same UUID.** Deleting a
  record and re-inserting a record with the **same primary key within one sync
  batch** (delete+insert within ~2s) syncs **only the delete** to CloudKit — the
  insert is dropped, so the record vanishes on all other devices on next sync
  (repro shows an alternating present/lost pattern). **Resplit blast radius:**
  directly hits the `Person`→denormalized-participant refactor above (combined
  PK/FK is the exact trigger) and any "replace the participant set" edit that
  deletes+reinserts a row with a stable id. **Guard:** a two-device test that
  deletes and re-inserts a same-UUID `ReceiptParticipant`/`SummaryItem` in one
  write transaction and asserts the row survives on the second device. If
  upstream hasn't fixed it, our `resplit-patches` either carries the fix or the
  adapter forces delete and re-insert into **separate sync batches**.
- **#356 — Conflict resolution differs between production and tests.** The
  built-in "field-wise last-edit-wins" upsert path (the `didSet`-flag logic in
  `CKRecord.update(with:row:columnNames:parentForeignKey:)`) behaves differently
  in the live sync engine than in the test harness — meaning **passing unit
  tests do NOT prove the production merge behavior** (a direct hit on our
  "test real flows, not green checks" memory). **Guard:** our conflict tests must
  run through the real `SyncEngine`/`MockCloudDatabase` round-trip the library
  ships, not a hand-rolled merge, and we assert on observed converged state.
- **#354 — "Last edit wins" is violated / nondeterministic.** Whether a
  server edit (newer timestamp) or a pending local edit wins depends on the
  **order of processing**, not the timestamps: identical t=30 local vs t=60
  server scenarios resolve to "Buy milk" (server) in one ordering and "Get milk"
  (client, but stamped t=60) in another — nondeterministic, contributes to a
  stale-data problem (#274). **Resplit blast radius:** two people editing the
  same shared Receipt's item amount can silently converge to the wrong total.
  **Guard:** a multi-writer Receipt test asserting deterministic convergence on a
  money field; if SQLiteData can't guarantee it, Phase-5 must add an
  app-level conflict policy (e.g. last-writer-by-server-timestamp on amounts) on
  top of the library, and this is a hard gate before any real-money shared split.

**Bottom line for Phase-5:** the sharing API is small and clean
(`share(record:)` / `acceptShare(metadata:)` / `SyncMetadata.share` permissions),
but the **schema must be reshaped so `Receipt` is a true root** and the **three
open conflict/data-loss bugs must be reproduced and guarded** before we trust
shared splits. Both are test-story-driven, fork-patchable, and contained to the
SQLiteData adapter module by the contract boundary.

---

## Design Red-Team Findings + Forced Adjustments

> 5-angle adversarial pass on SOOC+Records. **0 fatal, 5 serious-mitigable (high conf).** Two findings change the design — folded as adjustments below.

| Attack | Verdict | Failure mode | Mitigation / adjustment |
|--------|---------|--------------|------------------------|
| Does SOOC sever the Query macro in all 7 view sites with no behavior c | **serious-mitigable** | Only 2 real Query-in-view macros exist (ReceiptListView, FolderPickerView); the other 5 are doc-comments. ReceiptListView is the worst case: its feed  | Drop no-behavior-change for ReceiptListView. Phase 1 publishes live Model objects; value Records is Phase 2, gated on a nested-predicate Filter enum. Re-publish on attach |
| @MainActor / threading: I traced every persistence entry point (Receip | **serious-mitigable** | SOOC's central premise — "store owns identity/persistence and PUBLISHES a live observable collection that the 7 view sites subscribe to with NO behavi | 1) Make the re-entry safety a CONTRACT, not a hand-tuned accident: the SOOC store's publish step must batch all collection mutations into a single assignment (the H6 fix  |
| Memory + re-render scaling: does a store that owns and publishes LIVE  | **serious-mitigable** | The codebase has ALREADY converged on the opposite of SOOC for its largest collection, and did so to fix a production incident. Three grounded facts m | The failure is fatal ONLY under the literal reading ("store owns and eagerly materializes live collections for the whole graph"). It is fully mitigable, and the design's  |
| CloudKit remote-change propagation into store-owned collections and va | **serious-mitigable** | SOOC severs the only remote-sync bridge. Today remote CloudKit changes reach the UI only via SwiftData @Query, which is the subscription to mainContex | Require the SwiftData adapter to observe NSPersistentStoreRemoteChange and NSManagedObjectContextDidSave then debounce refetch diff republish. Gate parity on a real remot |
| Records-and-Resolvers value-type Record structs vs SwiftData reference | **serious-mitigable** | The attack mostly FAILS on its headline claim and SUCCEEDS on a narrow one. Headline ("loses cascade/identity") is false: (1) Cascade is owned by the  | 1) HARD INVARIANT: the Record read-model must NEVER own deletion/cascade — keep SwiftData (Phase-1) then SQLite FK ON DELETE CASCADE (endgame) as the sole cascade authori |

### Adjustments now baked into the design (do NOT plan against the old assumptions)

1. **`@Query` sites: 2 real, not 7.** Only `ReceiptListView` + `FolderPickerView` use the `@Query` macro; the other 5 were doc-comments. Phase-4 observation cutover scope shrinks to 2 real sites.
2. **SOOC must be SCOPED, never whole-graph.** The codebase already moved its largest collection OFF store-owned-live-collections to fix a production incident. The store publishes scoped/paged collections per view, not an eager materialization of the whole Receipt graph. `ReceiptListView` cannot be 'no-behavior-change' in Phase 1 — it publishes live Model objects first; value Records is Phase 2, gated.
3. **CloudKit remote-change bridge is mandatory.** SOOC severs the only remote-sync path (today remote CloudKit changes reach UI via `@Query`). The SwiftData adapter MUST observe `NSPersistentStoreRemoteChange` + `NSManagedObjectContextDidSave`, debounce, and republish — or remote/CKShare edits never reach the UI. This is a Phase-1 contract requirement.
4. **@MainActor re-entry safety is a CONTRACT.** The SOOC store batches all collection publishes on the main actor; re-entrancy safety must be explicit, not a hand-tuned accident.
5. **Records NEVER own deletion/cascade.** The value-type read model is read-only for cascade; SwiftData (Phase 1) then SQLite `FK ON DELETE` (Phase 5) own cascade semantics.

---

## Phase-0 Safety Net + Prior-Art (research fleet wih6rh870)

Confirmed. `CloudKitManager` subscribes to `eventChangedNotification` and `CKAccountChanged` purely to drive an `isSyncing` status spinner — it never observes `NSPersistentStoreRemoteChange`/`NSManagedObjectContextDidSave` to refresh data, exactly as the red-team finding states. And `ReceiptListView` confirms two real `@Query` macros (folders + receipts), the lazy-List design, and the explicit "@Query auto-updates on CloudKit sync" comment that the SOOC severs. Everything checks out. Synthesizing the three PLAN-ready blocks now.

---

## Phase-0 Safety Net

**Goal:** Before any persistence refactor touches a single `@Query` or `@Model` file, lock down a characterization baseline so "no behavior change" is a *gate*, not a claim. All paths below are verified to exist in `~/Development/resplit-ios`.

### Reusable baseline (already exists — do NOT rewrite)

**Test container factory (the one true seam):**
- `ReceiptSplitter/Mocks/TestEnvironment.swift` → `TestEnvironment.inMemoryContainer()` — returns a production-identical `ModelContainer` with `isStoredInMemoryOnly: true` + `cloudKitDatabase: .none`. **Use this in every new Phase-0 test; do not hand-roll containers.** Establish it as the single baseline container factory. (Confirmed lines 5/11/12.)

**Reusable model-logic tests (extend, don't duplicate):**
- `ReceiptSplitterTests/ReceiptItemTests.swift` — assignment state (shared/unresolved/assigned logic)
- `ReceiptSplitterTests/ReceiptParticipantTests.swift` — avatar fallback, legacy migration
- `ReceiptSplitterTests/PersonTests.swift` — `identityKey` 3-branch precedence, `lastUsedAt`
- `ReceiptSplitterTests/FolderTests.swift` — currency tally, majority + tie-break
- `ReceiptSplitterTests/Folder/FolderAggregationInvariantsTests.swift` — settlement math across folder receipts
- `ReceiptSplitterTests/SummaryItemCalculatorTests.swift` — tip pre/post-tax, subtotal calculation
- `ResplitCoreTests/ReceiptPersistenceTests.swift` — `ModelContext` save/detach contract
- `ResplitCoreTests/FolderManagerTests.swift` — folder state machine (create/delete/archive/complete); use as the **template** for new manager tests (`@MainActor` setUp/tearDown + in-memory container + direct manager instantiation)

**Reusable infra patterns from ResplitCoreTests:**
- `CloudKitManagerTests.swift` (lines 38–118) — `CloudSyncReducer` pure-function state-machine tests; reuse the pattern for any new reducer
- `CloudKitManagerTests.swift` (lines 126–194) — `CloudSyncEventSnapshot` error-metadata preservation (contrapositive Sentry-noise filtering); reuse for error classification
- `SettlementServiceTests.swift` (lines 8–65) — receipt/participant DTO builders; reuse for integration fixtures
- `StartupDataMigrationUseCaseTests.swift` (lines 9–29) + `ReceiptListContainerViewModelObservationCrashTests.swift` (lines 36–72) — the container → `Database` facade → repository → manager **DI stack**; make this the standard wiring for all new tests
- `LiveSessionViewModelTests.swift` (lines 48–75) — comprehensive `PersistedLiveSession.clear()` + `UserDefaults.removeObject` cleanup; reuse for all LiveSession tests

**Reusable UI/snapshot infra (for the observation-parity gate):**
- `LocaleSnapshotTestCase` base class (locale override, settle-time, precision guardrails, per-locale suffix naming) — baseline for all snapshot regression safety
- `UITestAppLauncher.makeApp(scenario:additionalArguments:)` + `UITestFixtureIdentifiers` — launch-arg composition + fixture routing
- `ReceiptDetailRobot` / `ReceiptListRobot` / `TripDetailRobot` — navigation orchestration helpers
- `UITestData.seedScenarioData(modelContext:scenario:)` — deterministic seeding for `.expanded`, `.tripHappyPath`, `.liveGuestResolution`, `.japanUsdTransfer`
- The **238 existing AccessibilityIdentifiers selectors** — the selector vocabulary for new Autobot tests; no duplication needed
- `Receipt.listRenderProperties` (`Receipt.swift` lines 146+) — the H8/H5 fault-avoidance allowlist; reference pattern for optimizing other list fetches

### Prioritized characterization-test gap list (add BEFORE migration)

Ordered by blast radius. **P0 = relationship/cascade integrity** (a wrong delete-rule mapping silently destroys user data); **P1 = observation parity** (the "no behavior change" claim at the 7 view sites); **P2 = adapter-seam contracts** (catch drift when the SQLiteData stub goes live).

**P0 — Cascade / nullify / relationship integrity (the writer-owned semantics the migration must preserve byte-for-byte):**

| # | Test (new) | Asserts |
|---|---|---|
| 1 | `testReceiptDeletionCascadesToParticipantsItemsSummaryItems()` | Insert receipt + 3 participants + 5 items + 4 summaryItems; delete receipt; fetch by `receipt.stableId`; assert all 12 children gone AND not findable via `FetchDescriptor<ReceiptParticipant>(#Predicate { $0.receipt == nil })`. |
| 2 | `testFolderDeletionNullifiesReceiptFolderLink()` | Folder + 3 receipts; delete folder; assert all 3 receipts survive with `folder == nil`; `FetchDescriptor<Receipt>(#Predicate { $0.folder == nil })` finds them. |
| 3 | `testPersonDeletionNullifiesParticipantPersonLink()` | Person + 2 receipts × 3 participants linked to person; delete person; assert all 6 participants survive with `person == nil`. |
| 4 | `testReceiptParticipantOrderedItemsInverseIntegrity()` | Many-to-many `ReceiptParticipant ↔ ReceiptItem`: add item to `participant.orderedItems`, verify `item.individualParticipants` contains it; delete item, verify removed; edit order array, persist, re-fetch, assert order preserved. |
| 5 | `testSummaryItemReceiptInverseIsConsistent()` | Receipt + 4 summaryItems (non-cascade inverse); fetch by receipt, assert all 4; mutate `summaryItem.receipt`, verify forward/reverse consistency. |
| 6 | `testReceiptItemReceiptInverseAfterCascadingDelete()` | Receipt + items via OCR-sim; delete receipt; fetch items via `FetchDescriptor` (no receipt) — assert all deleted (cascade verified) or expose orphan bug. |
| 7 | `testTransitiveDeletionSafety()` | Receipt+participant+person; delete receipt (cascades participant); then delete person; assert orphaned participant has `person == nil` and stays queryable (two-step cascade+nullify). |
| 8 | `testFolderReceiptsAggregateAfterNullification()` | Folder + receipts in distinct currencies; delete folder; verify nullified receipts return; assert `Folder.resolvedPrimaryCurrencyCode` doesn't crash/miscount on re-fetch. |
| 9 | `testCascadeDeleteCloudKitChangeTracking()` | Insert receipt+children; mark deletion; trigger save; verify `modelContext` change tracking shows **deletions** (not attribute updates) so CloudKit sync metadata isn't corrupted. |
| 10 | `ReceiptUniqueIdContractTests.swift` | Duplicate-`uniqueId` insert rejected/deduped; uniqueId stable across serialize round-trip; fetch-by-uniqueId returns exactly one; UUID format. **(This is the row-identity invariant the red-team flags as load-bearing — pin it now.)** |

**P1 — `@Query` → observation parity at the 7 view sites** (only **2 are real `@Query` macros** — `ReceiptListView.swift:11,19` and `FolderPickerView.swift:22`; the other 5 are doc-comments):

- Folder-detail `@Query` ordering: seed 3 receipts staggered `createdAt`; assert newest-first; insert programmatically; poll; assert surfaces at index 0 (contrapositive on activity-date / relationship re-observe break).
- Receipt-detail item-list observation during claim-state edits: mutate `item.order` via `mainContext`; assert computed re-sort.
- List search + folder context switching: add receipt to folder A; assert appears in home position 0 AND **not** in folder B (catches `@Query` context not switching).
- Folder completion/reopen: set `completedAt`, assert vanishes via `@Query` filter; clear it, assert re-appears (catches stale predicate cache).
- Multi-currency conversion-rate observation (`japanUsdTransfer`): mutate `receipt.conversionRate`; assert workbench re-renders.
- Snapshot pair `ReceiptDetailPopover_ClaimState_Unclaimed/Claimed` from same fixture (visual parity gate).

**P2 — Adapter-seam + facade contracts** (so the SwiftData→in-memory→SQLiteData swap has a contract, not vibes):

- `DatabaseFacadeTests.swift` (against `ResplitPersistence/API/Database.swift`): `saveIfNeeded` true/false on `hasChanges`; transaction execute + commit; insert/delete on main context; fetch applies predicate; **`snapshotReader` creates isolated context** (not shared with `mainContext`); `@MainActor` enforcement audit.
- `ContainerDatabaseWiringTests.swift`: `Container.shared.database()` non-nil & `DatabaseType`; registered `ModelContainer` is the same one passed to `Database.init`; snapshotReader usable; main vs snapshot contexts are different instances.
- `CloudKitManagerIntegrationTests.swift`: verify `setupNotificationObservers` subscribes to `eventChangedNotification` + `CKAccountChanged` (confirmed at `CloudKitManager.swift:210,224`); synthetic event ingested → `reducerState` updates; stale-event sweep prunes >300s; `shouldTrack()` filter respected (import/export/setup only).
- **`SchemaCloudKitContractTests.swift`** (CI gate, runs every PR): iterate `ResplitSchemaV1.models` via Mirror → assert every property is Optional or has a default; assert **no** `@Attribute(.unique)` constraints; assert `stableId` exists. This is the test that catches a CloudKit-illegal schema change *before* it ships.
- **Adapter-agnostic harness**: `TestModelContainerFactory` protocol with `SwiftDataInMemoryFactory` (now) + `MockFactory` (stub) implementations; one shared behavior-contract suite both must pass (insert+fetch returns same; cascade delete; predicate filter). This makes the adapter boundary explicit — tests declare "I want an ephemeral store," not "I want SwiftData in-memory."

---

## Design Red-Team Findings

Five attacks were run against the **Store-Owned Observable Collections (SOOC) Phase-1 spine + Records-and-Resolvers endgame**. **No FATAL findings — the SOOC + Records choice stands.** All five are `serious-mitigable | high`, and four of them collapse to mitigations the design's *own* escape hatch already implies ("Phase-1 leaves the 7 `@Query` sites with no behavior change"). The job is to make that contractual, not aspirational.

### Finding 1 — Does SOOC sever `@Query` cleanly at all view sites? `serious-mitigable | high`
**Attack:** Can the store-owned model serve every filter/sort/section/relationship need without SwiftData types?
**Verdict (grounded):** Only **2 real `@Query`-in-view macros** exist — `ReceiptListView.swift` (lines 11, 19) and `FolderPickerView.swift` (line 22); the other 5 "sites" are doc-comments. `ReceiptListView` is the worst case: its feed drives ~25 in-view filter/sort/section ops + 5 relationship traversals that work *only* because `@Query` returns live faulting `Model` objects.
**Mitigation:** Drop "no-behavior-change" for `ReceiptListView` specifically. Phase 1 publishes **live `Model` objects**; value Records are Phase 2, gated on a nested-predicate `Filter` enum. Re-publish on attach/detach/cascade-delete. Keep the partial-field fetch or H8/H5 regresses. Add a SwiftData-vs-store parity test under both adapters.

### Finding 2 — `@MainActor` / threading & re-entrancy `serious-mitigable | high`
**Attack:** Does SOOC's "store owns a live published collection" re-create the exact construct that already crashed prod?
**Verdict (grounded):** Yes — and that's the sharpest finding. The codebase has a working instance today: `ReceiptsRepository` (`@MainActor @Observable`, stored `receipts` array read by `ReceiptListContainerViewModel:325/348`). That path produced **Sentry RESPLIT-IOS-H6** (`libswiftObservation _NativeSet.insertNew → copyAndResize` crash from a multi-`willSet` re-entry window) and survives only because it was hand-tuned to a single `state = nextState` assignment. SOOC generalizes this to all sites and adds three new pressure sources: (1) everything is `@MainActor` with no `ModelActor`, so the publish step runs in the same tick as the SwiftData save + `NSPersistentCloudKitContainer` remote merges land on the main context mid-mutation; (2) the unbounded synchronous re-fetch on `@MainActor` is the H8/H5 main-thread-stall vector; (3) the GRDB endgame fires on a background queue → the SwiftData and SQLiteData adapters have **structurally different isolation**, so "adapters with no behavior change" is false at the concurrency layer.
**Mitigation:** (1) Make re-entry safety a **contract**: batch all collection mutations into one assignment (the H6 fix), never mutate the published collection from inside a `withObservationTracking`/SwiftUI body, add a debug-only re-entrancy assertion. (2) **Keep persistence single-actor for Phase 1** — no GRDB ValueObservation until the SQLiteData adapter is greenlit; the SwiftData adapter publishes on `@MainActor` exactly as today (this makes "no behavior change" *true* for Phase 1). (3) When GRDB is real, put the background→main hop *inside* the adapter; protocol contract = "published updates delivered on MainActor, asynchronously after persistence"; port the reconciler's read-after-save to an explicit `await` + add an async-delivery test variant. (4) Bake `Receipt.listRenderProperties` into the store's default fetch path. (5) Add Swift 6 `strict-concurrency = complete` on any new SQLiteData target so the compiler — not Sentry — catches `@Model`-crossing-actor mistakes.

### Finding 3 — Memory + re-render scaling `serious-mitigable | high`
**Attack:** Does a store that owns live collections for the whole `Receipt` graph blow memory / cause re-render storms vs today's `@Query` lazy-fetch + `List` windowing?
**Verdict (grounded):** Fatal **only** under the literal reading ("store eagerly materializes live collections for the whole graph"). Three grounded facts: (1) home list is *deliberately* `@Query`-lazy — `ReceiptListView.swift:19` (`@Query(sort: \Receipt.timestamp, order: .reverse)`, no fetchLimit, comment at lines 16–18 confirms "`List` + `@Query` never materializes all rows," and the team **removed** the in-memory full-corpus path on purpose); (2) `@Observable` coarse-grained tracking against a store's `[Receipt]` invalidates every subscriber on every insert/delete AND every CloudKit import batch (vs `@Query`+`List` per-row diffing); (3) eager graph = the H8/H5 hang by construction — `Receipt.swift:146+` `listRenderProperties` deliberately excludes the `receiptImageData` 200KB–2MB blob; 1000 receipts × ~0.5–2MB = ~0.5–2GB held eagerly → jetsam.
**Mitigation:** The design's own escape hatch is the fix — make it contractual: (1) the store must **not** own the home-list as a materialized `[Receipt]` — either keep native `@Query` untouched, or publish a thin facade over a `FetchDescriptor` carrying `propertiesToFetch: Receipt.listRenderProperties` + fetchLimit/offset window. **Add a lint (extend `wiring-regression-lint.sh`) pinning `listRenderProperties` at the list fetch site** so a refactor can't silently drop it. (2) Push the home list onto value-type Records *sooner* — Records are projections that naturally enforce the H8/H5 faulting discipline; scope live-`@Model` collection ownership to **single-aggregate surfaces** (detail view), never the corpus-wide list. (3) Add a memory regression test: seed 1000+ receipts with blob fixtures in-memory, drive the list fetch through the store, assert peak footprint + assert the descriptor excludes `receiptImageData`.

### Finding 4 — CloudKit remote-change propagation `serious-mitigable | high`
**Attack:** Do store-owned collections / value Records still receive remote CloudKit changes the way `@Query` does?
**Verdict (grounded):** SOOC severs the *only* remote-sync bridge. Today remote changes reach the UI **only** via SwiftData `@Query`'s subscription to mainContext change-tracking, which `NSPersistentCloudKitContainer` re-drives on import. **Confirmed in code:** nothing observes `NSPersistentStoreRemoteChange` or `NSManagedObjectContextDidSave` — the only `CKAccountChanged`/`eventChangedNotification` subscription in `CloudKitManager.swift:210,224` feeds an `isSyncing` **status spinner**, never data. A store-owned array is *not* re-driven by a remote merge; value Records are worse (fetch-time snapshots decoupled from change-tracking). The import lands in SQLite and the published array stays stale. **ASC ANPm-HS30l** already proves this hazard (store-mediated derived read model that staled/flickered during sync). The 24 in-memory configs use `cloudKitDatabase: .none` so they **cannot** catch it.
**Mitigation:** Require the SwiftData adapter to observe `NSPersistentStoreRemoteChange` + `NSManagedObjectContextDidSave`, then debounce → refetch → diff → republish. **Gate parity on a real remote-sync integration test (not the in-memory suite)** and prove it on a real CloudKit store before greenlighting the Records adapter. Re-run the ASC ANPm-HS30l repro on device. Keep literal `@Query` until the observer is proven on device.

### Finding 5 — Value-type Records vs SwiftData reference identity / cascade `serious-mitigable | high`
**Attack:** Does converting `@Model` relationships to value-type Records lose identity/cascade semantics?
**Verdict (grounded):** Headline ("loses cascade/identity") is **false**; a narrow real risk survives. Cascade is owned by the **writer**, and Phase 1 keeps SwiftData as writer, so `.cascade` rules are untouched; the Records layer is a **read model** (all 8 `toDTO()` consumers are read-only — settlement, stats, share-message, balance — none delete), so it literally can't lose cascade. The SQLite endgame gets *stronger* cascade (native FK `ON DELETE CASCADE` > SwiftData's app-level cascade, which has documented "does-not-cascade" bugs — the repo already distrusts it: `AccountDataDeletionService.swift:85–90` manually orders children-before-parents because batch `delete(model:)` bypasses cascade). Reference-identity loss is a non-issue — the codebase *already* ships value-type DTOs (`ReceiptDTO`/`ParticipantDTO`) in the money path with a deliberate **semantic** merge key (`receiptDTOIdentityKey`, person→contact→name→fallback), not `.id`.
**Narrow real failure modes:** (a) `receiptDTOIdentityKey` is a **lossy, collision-prone** collapse ("name-leo" collides for two distinct unlinked people both named "leo"). Today that's cosmetic/read-only. If Records-and-Resolvers ever promotes it to a SQLiteData **primary/foreign key**, a cosmetic merge becomes a **persistence merge = silent data loss**. (b) A **dual identity namespace** must be maintained forever: `stableId`/`uniqueId` (per-row, ~12 `ForEach` sites) vs `receiptDTOIdentityKey` (semantic group, settlement) — a Resolver returning the wrong namespace is a silent money-path bug.
**Mitigation:** (1) **Hard invariant:** the Record read-model NEVER owns deletion/cascade — SwiftData (Phase 1) then SQLite FK `ON DELETE CASCADE` (endgame) is the sole cascade authority; lint-ban `context.delete`/`DELETE` inside any `*Record`/`*Resolver` type. (2) **NEVER** let `receiptDTOIdentityKey` become a SQLiteData primary/foreign key — persistence identity MUST be per-row `uniqueId`/`stableId` (UUID String, CloudKit-safe); the identity key stays a derived read-time grouping key. (3) Make the dual namespace type-safe: two wrapper types (`RowID(uniqueId)` vs `MergeKey(identityKey)`) so a Resolver *can't* hand a `MergeKey` where a `RowID` is expected — turns the silent bug into a compile error. (4) Golden-master the settlement/stats assertions against BOTH adapters before greenlight (same receipts → identical `ParticipantDTO.amountOwed` + balances). (5) Regression test the name-collision case (two unlinked same-name participants stay **distinct** rows post-cascade and post-Record-mapping).

**Cross-finding pattern:** four of five findings (1, 2, 3, 5) reduce to the same root mitigation — **make "Phase-1 leaves the `@Query` sites unchanged + persistence single-actor" a contract enforced by lint + a both-adapter parity suite, not a promise.** Finding 4 is the one that needs net-new work: a real on-device CloudKit remote-change observer + integration test, because the in-memory test surface structurally cannot see it.

---

## Prior-Art & Best Practices (the observation layer)

Cited guidance for replacing SwiftData `@Query` with a store/repository-published `@Observable` collection, and for the GRDB/SQLiteData endgame.

### The thesis (why do SOOC at all)
- **Geoff Pado, "@Query Considered Harmful"** — https://pado.name/blog/2025/02/swiftdata-query/ — *DIRECT, this is the prior-art statement of the SOOC thesis.* Names the core defect verbatim: "Your view now has two concerns: displaying your interface AND managing your persistent storage." Names the decoupling payoff the SOOC→SQLiteData migration depends on: you can "completely replace the whole thing with something else, and avoid having to rewrite all your views." **Divergence to AVOID:** Pado has the store expose pre-transformed *view models* with views NOT subscribing (snapshot model). SOOC wants views to *subscribe* to a live collection — adopt his coupling critique, reject his "snapshot, don't subscribe" shape (that's a behavior change at the view sites). SOOC's subscription model is closer to Sharing's `@SharedReader` below.
- **AzamSharp, "SwiftData Architecture Patterns and Practices"** — https://azamsharp.com/2025/03/28/swiftdata-architecture-patterns-and-practices.html — *DIRECT validation of the Phase-1 spine.* `@MainActor DataAccess` protocol returns framework-agnostic plain value types; views get the store via environment injection, never `@Model`/`@Query`. His "plain type" boundary **IS** your value-type Record. Names the exact failure you're avoiding (switching to GRDB/Realm later is hard if views rely on `@Model`/`@Query`). **Counter-argument to pre-empt in your rationale:** he does NOT recommend a separate store for SwiftData-*forever* apps ("pure overhead"). SOOC's cost is justified *only* because you intend to swap backends. He also documents a concrete gotcha: CloudKit silent pushes "do not automatically trigger view updates" for direct relationship properties — fix is a re-run `@Query`/fetch, not a held relationship array (corroborates Red-Team Finding 4).

### The "now" SwiftData adapter mechanics
- **HackingWithSwift, MVVM + SwiftData** — https://www.hackingwithswift.com/quick-start/swiftdata/how-to-use-mvvm-to-separate-swiftdata-from-your-views — `@Query` "can only be used with a SwiftUI view"; the fix is a store that does a `FetchDescriptor` fetch on load and re-fetches on change. Names the central risk: you must "be careful to keep your data synchronized." Validates the in-memory adapter as a first-class deliverable (stub for unit/snapshot tests).
- **Jacob Bartlett, "SwiftData outside SwiftUI"** — https://blog.jacobstechtavern.com/p/swiftdata-outside-swiftui — *DIRECT for adapter internals.* **Thread-safety rule:** do NOT store the `ModelContext` as a long-lived property (it "is not inherently thread-safe… lots of actor coordination overhead"). The store owns the `ModelContainer` and creates a context inline per operation, or — since the SOOC store is `@MainActor` — pins to `mainContext` and re-fetches. Read methods take `predicate` + `sort` so the **store** owns the query spec — the bridge to the Records `Filter`-enum.
- **fatbobman, "Mastering Data Tracking & Notifications"** — https://fatbobman.com/en/posts/mastering-data-tracking-and-notifications-in-core-data-and-swiftdata/ — *DIRECT and load-bearing — the synchronization spine of SOOC Phase 1.* The hard part (keeping the collection live after `@Query`'s auto-update is gone): **subscribe to `ModelContext.didSave` and re-fetch.** `userInfo` carries inserted/deleted/updated `PersistentIdentifier` arrays. Caveats that shape the design: no `objectsDidChange` equivalent (notified only at *save* boundaries); single-process only; iOS 18 autosave timing "unclear" → call `save()` explicitly to make `didSave` deterministic. SwiftData History is the heavier cross-process alternative but "impacts performance." Pattern: store subscribes to `didSave` → re-runs its `FetchDescriptor` on the main actor → reassigns the published collection → subscribed views update.

### Observation-framework correctness rules
- **NilCoalescing, "Observable in SwiftUI"** — https://nilcoalescing.com/blog/ObservableInSwiftUI/ — `@Observable` gives property-level tracking ("only re-rendered when the properties they read change") — same fine-grained re-render `@Query` gave. **Known failure mode to design around:** mutating a *nested* observable collection can cause view *reinitialization*. **Recommendation:** expose the collection as a plain stored `private(set) var items: [Record]` and **reassign it wholesale** on each refresh — wholesale reassignment of a value-type array is the cleanest signal to Observation and sidesteps the nested-collection gotcha. This is also why value-type Records fit better than `[Receipt]` `@Model` arrays under Observation.

### The subscription contract (closest match to SOOC's actual ask)
- **Point-Free Sharing** (`@Shared`/`@SharedReader`) — https://github.com/pointfreeco/swift-sharing — *STRONG prior art for the subscription contract + adapter abstraction.* A single-source-of-truth collection multiple observables SUBSCRIBE to (vs Pado's snapshot). The `SharedKey` protocol (serialize + emit-on-change + canonical source) is a ready-made template for the SOOC adapter protocol: SwiftData-key (now), in-memory-key (tests), SQLiteData-key (stubbed). `@SharedReader` == the read-only published collection. **Two carry-overs:** (1) per-test quarantined storage is the in-memory adapter's test contract; (2) the `@ObservationIgnored`-on-property-wrapper-inside-`@Observable` gotcha — plan the store's published collection as a **plain stored var** the `@Observable` macro tracks, with the adapter feeding it, not a nested property wrapper. **Dependency note:** if Phase 1 stays dependency-light, treat Sharing as the *design template* for your hand-rolled store, not a code dependency yet.
- **dev.to/jameson, SwiftUI + SwiftData Repository** — https://dev.to/jameson/swiftui-with-swiftdata-through-repository-36d1 — *DIRECT for the store API shape.* `@MainActor` data-source behind an `@Observable` view-model that "exposes a collection property that views bind to, replacing direct `@Query`." Constructor injection enables swapping test doubles/in-memory/preview. **Caveat:** leans toward manual re-fetch rather than reactive observation — pair this *structure* with fatbobman's `didSave` live-refresh.

### The GRDB / SQLiteData endgame
- **Point-Free SQLiteData** — https://github.com/pointfreeco/sqlite-data — *DIRECT for the Records-and-Resolvers endgame.* `@Table` value structs == Record structs; `.where`/`.order`/`.count` builder == the Filter-enum query spec; `@Dependency(\.defaultDatabase)` + in-memory `DatabaseQueue` == the adapter swap point. `@FetchAll`/`@FetchOne`/`@Fetch` replace `@Query` and **work outside SwiftUI** (in `@Observable` models/UIKit/stores), backed by Sharing's `SharedReader`. `@FetchAll` does the live-collection observation natively — when the SQLiteData adapter is greenlit, the manual `ModelContext.didSave` re-fetch machinery is **retired**. Cost SQLiteData names honestly: requires SQL ownership (schema/normalization, joins, aggregates).
- **`@Fetch` + `FetchKeyRequest`** — https://raw.githubusercontent.com/pointfreeco/sqlite-data/main/Sources/SQLiteData/FetchKeyRequest.swift — `FetchKeyRequest` **IS the Resolver**: a `Hashable + Sendable` request runs an arbitrary multi-query transaction in ONE observation and emits a composite Value. Your `Filter` enum feeds a `FetchKeyRequest` whose `fetch(_ db:)` resolves the Record structs — compile-time-checked, testable, value-type query specs that coalesce related reads into one transaction/snapshot.
- **GRDB ValueObservation** — https://groue.github.io/GRDB.swift/docs/5.14/Structs/ValueObservation.html — the live-query primitive; the store owns one `ValueObservation` per published collection + holds the `DatabaseCancellable`. **Default dispatch is async on the main queue/MainActor** (views get main-thread updates free; the fetch runs off-main). Use `.immediate` (started on main) for a synchronous first value (mirrors `@Query`, avoids empty-then-populate flash). Prefer `trackingConstantRegion(_:)` + a **`DatabasePool`** (WAL) for the perf path — "reduce database contention, by not blocking database writes." **Caveat:** non-constant-region queries MUST use `tracking(_:)` or "some changes may not be notified." Apply `.removeDuplicates()` (Records are `Equatable` value types) so views don't re-render on no-op writes — a free win `@Query` doesn't give.
- **GRDB Concurrency** — https://raw.githubusercontent.com/groue/GRDB.swift/master/GRDB/Documentation.docc/Concurrency.md — open **exactly one** `DatabaseQueue`/`DatabasePool` per file for app lifetime. In-memory test adapter = `DatabaseQueue` on `:memory:`; prod = `DatabasePool` (WAL, concurrent snapshot reads). The store owns the single `any DatabaseReader`/`any DatabaseWriter` injected as a dependency.

### Migration recipe + the cautions
- **Point-Free maintainer, SwiftData/CloudKit → SQLiteData** — https://github.com/pointfreeco/sqlite-data/discussions/218 — *the most load-bearing finding for the SQLiteData greenlight gate.* Verbatim recipe: (1) ship a kill switch / forced-update; (2) one-time migration — "load all existing SwiftData records into memory and import them into new SQLite tables"; (3) do ALL import BEFORE creating the `SyncEngine`; (4) the two systems use **different CloudKit zones** so old data won't auto-merge. Blunt warning: "Swapping out SwiftData for SQLiteData is going to be incredibly difficult, and doubly so if you have CloudKit sync turned out." **Reuse your in-memory adapter as the migration conduit** (SwiftData reads → in-memory/Records → SQLiteData writes). If Resplit is local-only, the migration collapses to step 2 only.
- **groue on the repository/DAO pattern (issue #240)** — https://github.com/groue/GRDB.swift/issues/240 — REJECTS hiding the Database: "Methods that access the database should have a Database parameter" — for **transactional consistency** (two sequential repo calls run in separate transactions → intermittent bugs). **Constraint on the SOOC store:** compose multi-fetch reads (e.g. a balance + its line items) inside a single `database.read`/`write` block at the adapter boundary, then hand assembled Records up. His god-object warning applies to the SOOC store itself — keep it to identity/persistence + published collections; push query composition down into adapter-local read blocks. His **rule-of-three** is permission to keep the SQLiteData adapter a **stub** until a third real driver proves the protocol.
- **GRDB README record-design** — https://github.com/groue/GRDB.swift/blob/master/README.md — "GRDB records are not uniqued, do not auto-update, and do not lazy-load" (unlike `@Model`). Liveness comes only from ValueObservation. **Perf tuning:** <1000 records plain `.tracking`; 1–10k add `.removeDuplicates()` + `.debounce()`; 10k+ explicit table deps/predicates. The "not uniqued" property is *why* object identity must live in the store (corroborates "store owns identity" + Red-Team Finding 5's "uniqueId is the row key, never the merge key").
- **fatbobman, "Key Considerations Before Using SwiftData"** — https://fatbobman.com/en/posts/key-considerations-before-using-swiftdata/ — performance hierarchy "direct-SQLite > Core Data > SwiftData"; once iCloud sync is on, lightweight-migration-breaking changes are disallowed (schema-evolution lock-in); iCloud forbids `@Attribute(.unique)` and requires all properties optional/defaulted; iOS 18 "disruptive internal changes." **Design implications:** (1) keep Record fields a strict superset/intersection that survives both backends (optional/defaulted where SwiftData+iCloud demands); (2) treat SwiftData schema migrations as production-risky — the in-memory adapter is the safe place to test migration data-shape, and the SQLiteData cutover sidesteps SwiftData's migration tooling via the one-time bulk import.

**Net for the observation layer:** Phase 1 = hand-rolled `@MainActor` store, plain-`var` published collection reassigned wholesale, fed by a `ModelContext.didSave` subscription + `FetchDescriptor` (with `listRenderProperties` baked in). Endgame = swap the adapter internals to `@FetchAll`/`ValueObservation` on a `DatabasePool`, retire the `didSave` plumbing, `FetchKeyRequest` == Resolver, `@Table` struct == Record. Sharing's `SharedKey` is the adapter-protocol template; groue's "pass the Database / one connection / rule-of-three" rules keep the store from becoming a god-object.

Verified paths: `~/Development/resplit-ios/ReceiptSplitter/Models/{Receipt,ReceiptParticipant,ReceiptItem,SummaryItem,Person,Folder}.swift`, `ReceiptSplitter/Mocks/TestEnvironment.swift`, `ResplitPersistence/API/Database.swift`, `ResplitCore/Receipt List Container/{ReceiptListView,ReceiptsRepository,ReceiptsManager,ReceiptListContainerViewModel}.swift`, `ResplitCore/UI/FolderPickerView.swift`, `ResplitCore/Persistence+CloudKit/CloudKitManager.swift`, `ResplitCore/Managers/AccountDataDeletionService.swift`, `ReceiptSplitter/DTOs/{ReceiptDTO,ParticipantDTO}.swift`, `ResplitCore/Extensions/Receipt+DTO.swift`. Confirmed in-code: `Receipt.listRenderProperties` H8/H5 allowlist (Receipt.swift:146); 2 real `@Query` macros (ReceiptListView.swift:11,19 + FolderPickerView.swift:22); CloudKitManager subscribes to `eventChangedNotification`/`CKAccountChanged` for status-only (line 210/224), confirming no `NSPersistentStoreRemoteChange`/`NSManagedObjectContextDidSave` data observer exists.

---

## Queue / ETA Ledger
_Summed ETA: **15.0h** (clears the ≥8h done-state). Rows are agent-executable, disjoint-scoped._

| # | Row | Phase | ETA | Acceptance | Scope | Deps |
|---|-----|-------|-----|-----------|-------|------|
| P0.1 | Characterize the 6-model delete-rule graph as a frozen XCTest baseline | 0 | 1h | New ReceiptSplitterTests/Characterization/DeleteRuleGraphCharacterizationTests.swift seeds | ReceiptSplitterTests/Characterization/DeleteRuleGraphCharacterizationT |  |
| P0.2 | Golden settlement-determinism harness: 10x in-memory run snapshot | 0 | 1.25h | New ReceiptSplitterTests/Characterization/SettlementDeterminismCharacterizationTests.swift | ReceiptSplitterTests/Characterization/SettlementDeterminismCharacteriz |  |
| P0.3 | @Query view-site regression snapshots: pin ReceiptListView + FolderPickerView render output pre-migration | 0 | 1.25h | New ResplitCoreTests/Characterization/QueryViewSiteSnapshotTests.swift renders ReceiptList | ResplitCoreTests/Characterization/QueryViewSiteSnapshotTests.swift; Re | P0.1 |
| P0.4 | Folder archive/unarchive + currency-resolution characterization | 0 | 0.75h | New ReceiptSplitterTests/Characterization/FolderArchiveCharacterizationTests.swift: create | ReceiptSplitterTests/Characterization/FolderArchiveCharacterizationTes | P0.1 |
| P0.5 | Live Split offline-queue + reconciler characterization baseline | 0 | 1h | New ResplitCoreTests/Characterization/LiveSplitQueueCharacterizationTests.swift drives Liv | ResplitCoreTests/Characterization/LiveSplitQueueCharacterizationTests. |  |
| P0.6 | CloudKit event-sequence characterization + UI selector inventory guard | 0 | 1h | New ResplitCoreTests/Characterization/CloudKitEventCharacterizationTests.swift injects a s | ResplitCoreTests/Characterization/CloudKitEventCharacterizationTests.s |  |
| P1.1 | Create ResplitPersistenceContract module: ReceiptStore protocol + Record read model + Filter spec | 1 | 1h | New ResplitPersistenceContract framework target added to Project.swift (depended on by Res | ResplitPersistenceContract/Sources/ReceiptStore.swift; ResplitPersiste | P0.1,P0.2,P0.3 |
| P1.2 | Store-Owned Observable Collections (SOOC) spine wrapping the existing Database facade | 1 | 1h | New @Observable SwiftDataReceiptStore in ResplitPersistence conforms to ReceiptStore and o | ResplitPersistence/SOOC/SwiftDataReceiptStore.swift; ResplitPersistenc | P1.1 |
| P2.1 | First vertical slice: route ReceiptListView read path through the contract (one site, flag-gated) | 2 | 1h | ReceiptListView's receipt-list read is switched from @Query to the SOOC ObservableReceiptC | ResplitCore/Receipt List Container/ReceiptListView.swift; ResplitCore/ | P1.2 |
| P3.1 | In-memory adapter conforming ReceiptStore + 3-adapter cascade/nullify parity proof | 3 | 1h | New InMemoryReceiptStore (pure value-type backing) conforms to ReceiptStore. New ResplitPe | ResplitPersistenceContract/Sources/InMemoryReceiptStore.swift; Resplit | P2.1 |
| P3.2 | Records-and-Resolvers query engine + 50-receipt multi-adapter query parity | 3 | 1h | Implement the Filter-enum resolver over ReceiptRecord (folder='Summer', sort date desc, se | ResplitPersistenceContract/Sources/FilterResolver.swift; ResplitPersis | P3.1 |
| P4.1 | Observation cutover: migrate remaining 6 @Query sites to SOOC, flag default ON | 4 | 1h | FolderPickerView, ReceiptsManager, ReceiptListContainerViewModel, ReceiptsRepository (and  | ResplitCore/UI/FolderPickerView.swift; ResplitCore/Receipt List Contai | P3.2 |
| P4.2 | Wire CloudKit event stream + ModelContainer construction sites through the store seam | 4 | 0.75h | CloudKitManager's CloudSyncEventSnapshot stream is exposed through SwiftDataReceiptStore s | ResplitCore/DI/Container+Database.swift; ResplitCore/DI/FactoryConfigu | P4.1 |
| P5.1 | SQLiteData adapter + CKShare zone scaffolding behind the contract (endgame, flag OFF) | 5 | 1h | New SQLiteDataReceiptStore conforms to ReceiptStore using the Records-and-Resolvers read m | ResplitPersistenceContract/Sources/SQLiteDataReceiptStore.swift; Respl | P4.2 |
| P5.2 | CKShare share/accept/edit harness + participant-list parity (test-doubled, real-flow [LEO-GATED]) | 5 | 1h | New ResplitCoreTests/CKShare/CKShareFlowTests.swift simulates Account A creates Receipt +  | ResplitCoreTests/CKShare/CKShareFlowTests.swift; docs/persistence/cksh | P5.1 |

---

## Progress log
- 2026-06-13 — Project + prompt file created; planning-only goal; Phase-0
  safety-net-first sequencing set; test-case-stories named north star; architecture
  fleet w2pmacqy6 running; test surface grounded (337 XCTest / 74 Autobot / 10
  snapshot / 24 in-memory). `[METER ▓░░░░░░░ 1] [ETA 2h seeded] [N pending, 0 in_progress, 0 done]`
- 2026-06-13 — CKShare/SQLiteData fit + fork-strategy section written + grounded
  against pointfreeco/sqlite-data @ main (tag 1.6.6, 27 open issues). Verified
  LIVE via GitHub API: sharing API surface (SyncEngine.share(record:configure:) →
  SharedRecord, CloudSharingView, acceptShare(metadata:), SyncMetadata.share
  permissions, CKSharingSupported Info.plist key), the root-record-only sharing
  constraint (Receipt = the only valid share root; Person FK is the schema
  landmine), and the 3 open `bug`-labeled sync-correctness issues #418 (same-UUID
  delete+reinsert data loss), #356 (prod-vs-test conflict divergence), #354
  (nondeterministic last-edit-wins). Fork strategy: fork + upstream remote +
  rebased `resplit-patches` branch, SwiftPM `exact:`-tag pin (1.6.6-resplit.N),
  weekly automated drift-rebase gated by SQLiteData + adapter suites, drop-on-
  upstream. One Done-State §3 coverage section closed. `[METER ▓▓░░░░░░ 2]`
- 2026-06-13 cycle 2 — Folded deepen fleet (woopnl0ca): 26 test-case stories, all 6 design sub-sections, 15 ETA rows = **15h** (clears ≥8h). Research+red-team fleet wih6rh870 still running (Phase-0 coverage audit + SOOC red-team + prior-art). `[METER ▓▓▓▓▓░░░ 5] [ETA 15h queued] [15 pending, 0 in_progress, 0 done]`
- 2026-06-13 cycle 3 — Folded research+red-team fleet (wih6rh870): Phase-0 safety net grounded (9 untested cascade/nullify gaps = top priority), 5-angle red-team (0 fatal / 5 serious-mitigable), prior-art. Design AMENDED (2 real @Query sites; scoped SOOC; mandatory CloudKit remote-change bridge). `[METER ▓▓▓▓▓▓▓░ 7] [ETA 15h queued] [15 pending, 0 in_progress, 0 done]`
