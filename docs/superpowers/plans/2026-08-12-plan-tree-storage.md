# Partitioned Plan Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace monolithic Shadow plan storage with one manifest-addressed, provenance-preserving plan tree whose exact lookups and mutations stay bounded as history grows.

**Architecture:** `PLAN.md` remains the board's stable root pointer and publishes one content-addressed B+ tree stored under `PLAN.d/objects/sha256/`. A shared `PlanSnapshot` owns legacy-monolith and tree reads, exact routing, materialization, provenance, and atomic mutation; every command uses that owner instead of inventing shard logic. Routing pages contain locators only, selected Markdown shards remain canonical content, and free-text caches are disposable and digest-bound.

**Tech Stack:** Python 3 standard library (`dataclasses`, `hashlib`, `json`, `os`, `pathlib`, `tempfile`, `fcntl`), existing Shadow grammar/root-board modules, `unittest`, Git.

## Global Constraints

- The private root board remains the sole owner of project priority, entity pointers, claims, owners, and resume rows.
- `PLAN.md` plus its content-addressed objects form one logical authority; no database, daemon, provider, summary, cache, or second queue may own task or proof state.
- Preserve every row ID, receipt byte, pointer, claim, owner, dependency, and command semantic during migration and rollback.
- Root files are at most 8 KiB, index pages 16 KiB, data shards 32 KiB, and index pages have at most 64 children.
- Source, merge, installed executable, deployment, and live dogfood receipts remain distinct.
- Build with TDD, focused falsifiers before the full suite, and one independently reviewable commit per task.

---

## File structure

- `scripts/shadow_plan_store.py`: sole format, object, tree-build, snapshot, routing, materialization, provenance, transaction, migration, and rollback owner.
- `scripts/shadow-plan.py`: operator CLI for query, dry-run/apply migration, rollback, verify, and read-only garbage-collection discovery.
- `scripts/shadow_plan_scale.py`: benchmark/corpus owner; consumes the store rather than maintaining another splitter.
- `scripts/shadow_root_board.py`: board/path-safety owner; delegates logical reads to `PlanSnapshot`.
- Public command scripts: consume the shared snapshot API, using targeted routes unless an invariant truly requires full materialization.
- `tests/test_plan_store.py`: format, corruption, lookup, provenance, transaction, migration, rollback, and scale fixtures.
- Existing command tests: monolith/tree semantic parity for every public door.
- `docs/reference/plan-scale.md`: normative contract and measured receipts.

### Task 1: Canonical object tree and lossless builder

**Files:**
- Create: `scripts/shadow_plan_store.py`
- Create: `tests/test_plan_store.py`
- Modify: `scripts/shadow_plan_scale.py`
- Modify: `tests/test_plan_scale.py`

**Interfaces:**
- Consumes: `shadow_plan_grammar.HASH_RE`, `HOT_TASK_ROW_RE`, and the exact grammar boundaries currently modeled by `shadow_plan_scale._shard_boundaries`.
- Produces: `PlanStoreError`, `FormatLimits`, `PlanTreeBuild`, `build_tree(content: bytes, *, limits: FormatLimits = DEFAULT_LIMITS) -> PlanTreeBuild`, and `materialize_build(build: PlanTreeBuild) -> bytes`.

- [ ] **Step 1: Write failing losslessness and budget tests**

```python
class PlanTreeBuildTests(unittest.TestCase):
    def test_build_is_lossless_and_content_addressed(self) -> None:
        source = plan("alpha", "~aa11", padding="x" * 50_000).encode()
        build = store.build_tree(source)
        self.assertEqual(store.materialize_build(build), source)
        self.assertLessEqual(len(build.root_bytes), store.ROOT_MAX_BYTES)
        for digest, body in build.objects.items():
            self.assertEqual(hashlib.sha256(body).hexdigest(), digest)

    def test_single_oversize_grammar_item_refuses(self) -> None:
        source = plan("alpha", "~aa11", padding="- " + "x" * 40_000).encode()
        with self.assertRaisesRegex(store.PlanStoreError, "grammar item exceeds"):
            store.build_tree(source)
```

- [ ] **Step 2: Run the focused tests to prove the missing behavior**

Run: `scripts/shadow-python.sh -m unittest tests.test_plan_store.PlanTreeBuildTests -v`

Expected: FAIL because `shadow_plan_store` and `build_tree` do not exist.

- [ ] **Step 3: Implement canonical object and page primitives**

Use these exact constants and serializer:

```python
ROOT_SCHEMA = "shadow.plan-tree.v1"
PAGE_SCHEMA = "shadow.plan-tree-page.v1"
ROOT_MAX_BYTES = 8 * 1024
INDEX_MAX_BYTES = 16 * 1024
DATA_MAX_BYTES = 32 * 1024
PAGE_FANOUT = 64

def digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
```

- [ ] **Step 4: Implement deterministic grammar-boundary splitting and B+ tree construction**

Split before preamble, section, milestone, and append-only Deferred,
Contradictions, or Progress item boundaries. Build catalog leaves keyed by
zero-padded sequence, row leaves keyed by exact `~id`, and tag leaves keyed by
tag/timestamp/receipt digest. Build branch pages bottom-up in chunks of at most
64 and refuse any page or data item over its limit.

- [ ] **Step 5: Implement exact materialization and deterministic rebuild proof**

Walk catalog order, verify each content digest, concatenate unchanged bytes,
and compare logical bytes/digest. Build the same source twice and assert equal
root bytes, object set, logical IDs, routes, and materialization.

- [ ] **Step 6: Make the benchmark consume the canonical splitter**

Replace `shadow_plan_scale.sharded_layout()` internals with `build_tree()` while
retaining the existing comparison report. Delete the second boundary parser.

- [ ] **Step 7: Run focused tests and commit**

Run: `scripts/shadow-python.sh -m unittest tests.test_plan_store tests.test_plan_scale -v`

Expected: PASS and the comparison still chooses `manifest-plus-shards`.

Commit: `git commit -m "feat: build canonical partitioned plan trees"`

### Task 2: Safe snapshots, exact routes, and provenance

**Files:**
- Modify: `scripts/shadow_plan_store.py`
- Modify: `tests/test_plan_store.py`

**Interfaces:**
- Consumes: `build_tree` and canonical root/page/object formats.
- Produces: `PlanSnapshot.open(plan: Path)`, `materialize() -> bytes`, `row(row_id: str) -> PlanResult`, `receipts(selector: str, newest_first: bool = True) -> tuple[PlanResult, ...]`, `section(name: str, active_only: bool = False) -> tuple[PlanResult, ...]`, and `PlanResult.provenance`.

- [ ] **Step 1: Write failing route and provenance tests**

```python
def test_row_lookup_is_bounded_and_traceable(self) -> None:
    installed = install_fixture_tree(self.root, plan("alpha", "~aa11").encode())
    result = store.PlanSnapshot.open(installed).row("~aa11")
    self.assertIn(b"current work for alpha", result.content)
    self.assertEqual(result.provenance.selector, "row:~aa11")
    self.assertLessEqual(result.provenance.file_reads, 10)
    self.assertLessEqual(result.provenance.source_bytes, 168 * 1024)

def test_tampered_object_refuses_before_content_returns(self) -> None:
    installed = install_fixture_tree(self.root, plan("alpha", "~aa11").encode())
    tamper_first_object(installed.parent / "PLAN.d")
    with self.assertRaisesRegex(store.PlanStoreError, "object digest mismatch"):
        store.PlanSnapshot.open(installed).row("~aa11")
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `scripts/shadow-python.sh -m unittest tests.test_plan_store.PlanSnapshotTests -v`

Expected: FAIL because `PlanSnapshot` and `PlanResult` do not exist.

- [ ] **Step 3: Implement safe root/object reads**

Open with `O_NOFOLLOW | O_CLOEXEC`, require regular files, freeze `fstat()`
before and after bounded reads, reject link components/path escapes, then check
declared bytes and digest. Accept only legacy UTF-8 Markdown or the exact fenced
root schema.

- [ ] **Step 4: Implement bounded B+ traversal**

```python
def _lookup(self, tree_root: str, key: str) -> tuple[dict[str, object], tuple[str, ...]]:
    digest = tree_root
    visited: list[str] = []
    while True:
        page = self._verified_json_object(digest, INDEX_MAX_BYTES)
        visited.append(digest)
        if page["kind"] == "leaf":
            return exact_leaf_entry(page, key), tuple(visited)
        digest = child_covering(page, key)
```

Reject duplicate keys, overlapping branch ranges, cycles/excess depth, and any
route whose selected shard does not contain the requested row or tag.

- [ ] **Step 5: Implement materialization, section iteration, and provenance**

Provenance includes public entity locator, root digest, visited page digests,
shard digest/bytes, selector, catalog key, result byte range, result digest,
file reads, and verified source bytes. Legacy plans return one-source receipts.

- [ ] **Step 6: Add the corruption matrix**

Cover missing object, wrong bytes/digest, unsupported schema, traversal,
symlink leaf, cycle, excess depth, duplicate route, route/content mismatch,
malformed UTF-8, and logical digest mismatch. Every fixture must refuse before
a `PlanResult` exists.

- [ ] **Step 7: Run tests and commit**

Run: `scripts/shadow-python.sh -m unittest tests.test_plan_store -v`

Commit: `git commit -m "feat: read plan trees with bounded provenance"`

### Task 3: Strictly read-only migration and frozen-query parity

**Files:**
- Create: `scripts/shadow-plan.py`
- Modify: `scripts/shadow_plan_store.py`
- Modify: `scripts/shadow_plan_scale.py`
- Modify: `tests/test_plan_store.py`
- Modify: `tests/test_plan_scale.py`
- Modify: `docs/reference/plan-scale.md`

**Interfaces:**
- Consumes: `PlanSnapshot`, `build_tree`, and the 16-case frozen query corpus.
- Produces: `dry_run_migration(plan: Path, *, board: Path | None) -> MigrationReport` and `shadow plan migrate PLAN.md --dry-run --board ~/.shadow/board.json`.

- [ ] **Step 1: Write failing no-write and parity tests**

```python
def test_dry_run_writes_nothing_and_matches_queries(self) -> None:
    source = self.root / "PLAN.md"
    source.write_text(plan("alpha", "~aa11"), encoding="utf-8")
    before = snapshot_tree(self.root)
    report = store.dry_run_migration(source, board=None)
    self.assertEqual(snapshot_tree(self.root), before)
    self.assertTrue(report.exact_materialization)
    self.assertEqual(report.query_mismatches, ())
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `scripts/shadow-python.sh -m unittest tests.test_plan_store.DryRunMigrationTests -v`

Expected: FAIL because the dry-run API and CLI do not exist.

- [ ] **Step 3: Implement the dry run entirely in memory**

Freeze plan state and optional board revision; build/materialize/validate;
execute legacy and tree queries; re-read both frozen tokens. Emit only public
locators, counts, digests, depths, budgets, and mismatches. Create no directory,
temporary project file, Git index entry, board entry, or cache.

- [ ] **Step 4: Implement CLI contracts**

Exit 0 for exact parity/budgets, 2 for input refusal, and 3 for changed source
or board token. Print diagnostics to stderr and sorted JSON to stdout. Add
subprocess tests proving private paths and plan prose never leak.

- [ ] **Step 5: Run real dry runs and record exact refusals**

Run against machine-local Shadow, largest Resplit, and Snowcubes plans. The
known missing Shadow archives must refuse until source-backed repair; record
rather than bypass any canonical defect.

- [ ] **Step 6: Run tests and commit**

Run: `scripts/shadow-python.sh -m unittest tests.test_plan_store tests.test_plan_scale -v`

Commit: `git commit -m "feat: dry-run lossless plan migrations"`

### Task 4: One read boundary for every command

**Files:**
- Modify: `scripts/shadow_root_board.py`
- Modify: `scripts/shadow-status.py`, `scripts/shadow-amp.py`, `scripts/shadow-accept.py`, `scripts/shadow-lifecycle.py`, `scripts/shadow-lint.py`, `scripts/shadow_board_import.py`, `scripts/verify-host.py`
- Modify: corresponding command test modules

**Interfaces:**
- Consumes: `PlanSnapshot.open`, `row`, `receipts`, `section`, and `materialize`.
- Produces: `shadow_root_board.open_plan(plan: Path) -> PlanSnapshot`; legacy `read_plan_bytes/text` become compatibility wrappers over `materialize()`.

- [ ] **Step 1: Add monolith/tree parity fixtures to every public command test**

For one source, invoke each command against legacy and tree stores with isolated
homes/boards. Normalize root/provenance digests only; assert equal exit code,
row state, board revision delta, claim behavior, status JSON, lint findings,
and reader-facing output.

- [ ] **Step 2: Inventory and classify direct plan reads**

Run: `rg -n "read_plan_(text|bytes)\(|\.read_(text|bytes)\(" scripts`

Mark each call targeted or whole-plan. The final search may show compatibility
wrappers and documented full validators only.

- [ ] **Step 3: Implement the shared board door**

```python
def open_plan(plan: Path) -> PlanSnapshot:
    if not regular_plan(plan):
        raise BoardError("plan must be a regular non-symlink PLAN.md")
    try:
        return PlanSnapshot.open(plan)
    except PlanStoreError as exc:
        raise BoardError(str(exc)) from exc
```

- [ ] **Step 4: Convert current-work paths to bounded routes**

`status --by`, portfolio resume, `throw`, `return`, and `amp` use the board's
exact row ID with `snapshot.row(id)` and load only its owning milestone shard.
They must not materialize an entity to find one resume row.

- [ ] **Step 5: Convert whole-plan validators intentionally**

Lint, lifecycle global invariants, import equality, and migration validation
may materialize when their contract spans all content. Comment the invariant;
do not claim those paths are bounded lookups.

- [ ] **Step 6: Run parity suites and commit**

Run the focused status, amp, throw, return, accept, lifecycle, lint, import,
and host-verification test modules.

Commit: `git commit -m "refactor: route commands through plan snapshots"`

### Task 5: Atomic mutation and crash recovery

**Files:**
- Modify: `scripts/shadow_plan_store.py`, `scripts/shadow_root_board.py`, and mutating command scripts
- Modify: `tests/test_plan_store.py` and mutating command tests

**Interfaces:**
- Consumes: `PlanSnapshot` and existing board lock/CAS owners.
- Produces: `PlanTransaction.begin(plan, expected_root, expected_generation)`, `replace_shard`, `append_receipt`, `validate`, `publish`, and `abort`.

- [ ] **Step 1: Write stale-writer and crash-point tests**

```python
def test_stale_writer_loses_root_cas(self) -> None:
    first = store.PlanTransaction.begin(self.plan)
    second = store.PlanTransaction.begin(self.plan)
    first.append_receipt(PROOF_LINE).publish()
    with self.assertRaisesRegex(store.PlanStoreError, "root changed"):
        second.append_receipt(OTHER_PROOF).publish()
```

- [ ] **Step 2: Publish immutable objects safely**

Write a private temp file in the target bucket, fsync/verify, atomically rename
to its digest, and fsync the directory. Existing correct objects are idempotent;
existing wrong bytes refuse.

- [ ] **Step 3: Implement root CAS and board ordering**

Use the existing lock order; freeze root/board; publish objects; validate the
candidate tree; atomically replace/fsync `PLAN.md`; then run the existing board
transaction and re-read both. Never delete objects in the transaction.

- [ ] **Step 4: Integrate task flip and receipt append**

Accept changes only the task shard, affected index paths, and a new Progress
shard. Assert unaffected shard digests stay unchanged and write amplification
remains within the contract.

- [ ] **Step 5: Complete the crash matrix**

Inject failure after temp write, object rename, index page, before root CAS,
after root CAS/before board update, and after board update. Each state must have
one readable authority and an explicit recovery path.

- [ ] **Step 6: Run tests and commit**

Run store, accept, throw, and return test modules.

Commit: `git commit -m "feat: publish plan mutations atomically"`

### Task 6: Apply migration, rollback, and unreachable-object discovery

**Files:**
- Modify: `scripts/shadow-plan.py`, `scripts/shadow_plan_store.py`, `tests/test_plan_store.py`, `docs/reference/plan-scale.md`

**Interfaces:**
- Consumes: successful `MigrationReport`, `PlanTransaction`, and board state token.
- Produces: `apply_migration`, `rollback_migration`, and read-only `gc_candidates`.

- [ ] **Step 1: Write apply/rollback preservation tests**

Freeze plan bytes, board entity/pointer/resume/claims, and command outputs.
Apply the expected dry-run digest, reopen from a new process, rollback with the
expected root, and assert byte-exact source restoration plus semantic board and
command equality. Changed source or board revision refuses before writes.

- [ ] **Step 2: Implement gated apply**

Require expected source/root digests, current successful dry run, clean
Git/private-journal state, and no conflicting claim. Commit root and objects
together for Git-backed plans; emit only old/new digests and board revision.

- [ ] **Step 3: Implement explicit rollback**

Verify current root digest, restore original bytes with CAS, validate all board
references and command outputs, and retain objects until readback succeeds.
Ordinary reads never silently follow `previous_root`.

- [ ] **Step 4: Implement read-only unreachable-object discovery**

Walk current-root and retained-rollback reachability. Report digest and age
only; deletion remains a separate explicitly authorized action outside M26.

- [ ] **Step 5: Run tests and commit**

Run: `scripts/shadow-python.sh -m unittest tests.test_plan_store -v`

Commit: `git commit -m "feat: migrate and roll back plan trees"`

### Task 7: Scale, real-plan, cold-seat, and delivery proof

**Files:**
- Modify: `tests/test_plan_store.py`, `tests/test_plan_scale.py`, `docs/reference/plan-scale.md`
- Modify: machine-local Shadow `PLAN.md` only through its declared Shadow proof path

**Interfaces:**
- Consumes: all prior tasks and the frozen 16-query corpus.
- Produces: M26 receipts for source, merge, installed executable, and live cold-seat behavior.

- [ ] **Step 1: Add a million-shard structural benchmark**

Generate descriptor/fixed-content objects without allocating a million 32 KiB
bodies. Assert fanout/depth, root/page bytes, exact lookup file reads, and the
168 KiB one-result ceiling. Record elapsed time as an observation; hops/bytes
are portable acceptance gates.

- [ ] **Step 2: Run focused and full clean-checkout verification**

Run store/scale/command parity, then the documented full suite, style guard,
compileall, `git diff --check`, and plan lint. Record exact counts/skips.

- [ ] **Step 3: Resolve archive defects only from authority**

For each missing Shadow archive, locate a committed/private-journal source with
matching provenance. If unavailable, retain the exact migration refusal; never
copy a matching filename from a worktree as invented history.

- [ ] **Step 4: Migrate two representative authorities**

After dry-run parity, migrate machine-local Shadow and one Git-backed product
plan. Preserve entity IDs/pointers/claims and commit each owning source without
installing or deploying as a side effect.

- [ ] **Step 5: Run cold-seat and cache-deletion acceptance**

From a fresh process, query current work, exact row, latest decision,
contradiction, proof, and history. Delete all derived caches and repeat. Match
frozen result digests, provenance, hop/byte budgets, and board claims.

- [ ] **Step 6: Prove byte-exact rollback on both plans**

Compare restored bytes and normalized command outputs, verify board pointer,
resume, owner, and claims, then reapply only when required for live proof.

- [ ] **Step 7: Keep delivery receipts separate and audit completion**

Merge after review and clean tests; install the exact merged executable
separately; then capture live cold-seat executable/readback proof. Map every
contract clause and all eight mechanical acceptance items to current evidence.
Any missing or indirect receipt keeps M26 open.

- [ ] **Step 8: Commit final evidence**

Commit: `git commit -m "test: prove bounded plan storage end to end"`

## Self-review result

- Spec coverage: authority, partitioning, bounded indexes, provenance,
  losslessness, exact/discovery lookup, atomic mutation, corruption,
  concurrency, migration, rollback, command parity, cold-seat proof, real-plan
  proof, and delivery separation each map to a task.
- Placeholder scan: no deferred implementation markers or unspecified generic
  error-handling steps remain.
- Type consistency: `PlanSnapshot`, `PlanResult`, `PlanTransaction`,
  `MigrationReport`, and `PlanTreeBuild` are introduced before consumers and
  retain the same signatures throughout later tasks.
