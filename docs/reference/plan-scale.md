# Plan scale — frozen baseline and decision gates

Status: **M26 baseline frozen; manifest-addressed canonical shards chosen.**

This record answers `~psc1`. It measures the current whole-file system before
any split, manifest, or index exists. The root board and entity plans remain
the only authorities. The profiler is read-only and emits public locators,
digests, counts, timings, and result digests; it does not copy plan text into a
database or report.

## Repeat the baseline

Observed at `2026-08-13T02:39:51+00:00` on source
`be3a9e90178a9eda921befbcec8fe378e6ae2077`, with root-board revision 698.
Each timing is 101 repetitions after the full repository baseline passed 907
tests with one skip.

```sh
scripts/shadow-plan-scale.py \
  --board ~/.shadow/board.json \
  --project shadow \
  --project resplit-ios \
  --project snowcubes \
  --repeats 101
```

Focused regression:

```sh
scripts/shadow-python.sh -m unittest tests.test_plan_scale
```

The command selects the largest registered entity for each named project. It
refuses a missing or duplicate resume row, a malformed board, an unsafe
archive link, an unreadable plan, or an unbounded source. The report never
contains an absolute plan path.

## Frozen sources

| Source | SHA-256 | Bytes | Rows | Milestones | Progress | Unresolved plan contradictions | Archives |
|---|---|---:|---:|---:|---:|---:|---:|
| `board@698` | `eb559cce2ea89abce561f87a851656f6074f915facf5ebdf514cf93994007d93` | 3,074 | — | — | — | — | — |
| `entity@7eff07537c1e/PLAN.md` | `c4f4fed431e0e7a35296d2b4f85fa463657e5d090f35baed7f10bb54df01c2f1` | 260,541 | 117 | 19 | 344 | 11 | 5 links; 4 missing |
| `entity@470a0d2b4586/PLAN.md` | `deb160f73da6cf8c1bb14354a0b8e4c4b7c5bee9cd102b9a31e7e2bf5de9782f` | 249,241 | 72 | 8 | 274 | 6 | 0 |
| `entity@18269cfdd39b/PLAN.md` | `1383b4e6854c3c726e7d03957639540b602e1b9d34e15d0f751b088350e22321` | 248,845 | 121 | 27 | 171 | 21 | 0 |
| `entity@7eff07537c1e/docs/plan-archive/universal-system-one-root-board-per-computer.md` | `2d8ab029d3513e7d77a956edb28636ef8d1eed77aad3891d33db3cfd1660b87d` | 18,613 | — | — | — | — | — |

The four missing Shadow archive targets are a correctness finding, not a
benchmark inconvenience. The machine-local plan contains their tombstones but
its adjacent archive directory contains only the universal-system archive.
The corpus uses that one re-observable archive and records the missing-link
count separately; it never follows a worktree copy to manufacture history.
Contradiction counts and contradiction-query results use the plan grammar's
unresolved predicate: `winner:` and `provisional winner:` remain live, while
only a bullet beginning with `RESOLVED` is closed.

## Current complexity

The current parser calls `read_plan_text()`, `splitlines()`, `_sections()`, and
`_parse()` over the entire hot file before selecting one row. Therefore:

- one entity lookup is `O(plan bytes)` time and space at the parser boundary;
- a portfolio lookup is `O(sum of selected plan bytes)`;
- the 256 KiB lifecycle ceiling bounds the constant but does not change the
  complexity;
- result context is tiny, but the source bytes read are the whole file.

| Entity | Parse p50 / p95 | Read + parse p50 / p95 |
|---|---:|---:|
| Shadow | 1.188 / 1.294 ms | 1.411 / 1.637 ms |
| Resplit iOS | 1.311 / 1.438 ms | 1.484 / 1.637 ms |
| Snowcubes | 1.184 / 1.260 ms | 1.371 / 1.420 ms |

These local latencies are not a user-visible performance claim. They show
that 250 KiB is cheap on this machine today. The scaling defect is the amount
read: a one-row lookup still consumes 248,845–260,541 source bytes, while the
three-entity current-work lookup consumes 761,701 bytes across four hops.

## Frozen query corpus

Every result below is the digest of the exact selected line or bounded answer,
not a prose judgment. A later layout must return the same result digest from
the same source digest or explicitly refuse stale input.

| Case | Kind | Source ref(s) | Source bytes | Result bytes | Hops | Result SHA-256 |
|---|---|---|---:|---:|---:|---|
| `shadow-7eff0753-current` | current work | Shadow plan | 260,541 | 406 | 1 | `a73472c2db7ad95ea991b08bdb8543195b475113b63f8a9cd4ae44c85b55d249` |
| `shadow-7eff0753-decision` | decision | Shadow plan | 260,541 | 274 | 1 | `e3f784515df3babe15c6f6d91730e77d6eafd7094fc7106f0579187b4084ab97` |
| `shadow-7eff0753-contradiction` | contradiction | Shadow plan | 260,541 | 73 | 1 | `af1b9e016068245d8621ed8232d4c05a92fb8f92e958fc99bda13725b884f7e3` |
| `shadow-7eff0753-proof` | proof | Shadow plan | 260,541 | 251 | 1 | `22846ee0749aeb351c15e7e11fd7f3c9dc0a32b830bd347a348cb4b7bc0f91d1` |
| `shadow-7eff0753-history` | history | Shadow plan + universal-system archive | 279,154 | 373 | 2 | `9e9538e5f4ce0683a889a48e1eee534dbf9a0b02f779b59aaf70620c28062591` |
| `resplit-ios-470a0d2b-current` | current work | Resplit plan | 249,241 | 520 | 1 | `2103ac68be158e9a99f102a18610f4837acbd09793737ebd34d92323978be922` |
| `resplit-ios-470a0d2b-decision` | decision | Resplit plan | 249,241 | 540 | 1 | `16fada8483731421534902afc7d2560d1f0a3d50b562314919ee97b2864bfa47` |
| `resplit-ios-470a0d2b-contradiction` | contradiction | Resplit plan | 249,241 | 264 | 1 | `01470d09d009915854da820c9393fc2c00f1bde7678736bffa41ef908cdf4195` |
| `resplit-ios-470a0d2b-proof` | proof | Resplit plan | 249,241 | 540 | 1 | `16fada8483731421534902afc7d2560d1f0a3d50b562314919ee97b2864bfa47` |
| `resplit-ios-470a0d2b-history` | history | Resplit plan | 249,241 | 189 | 1 | `a778adc5e3691126375bd80a2463122012ad07c071e0cde430f9919358794b31` |
| `snowcubes-18269cfd-current` | current work | Snowcubes plan | 248,845 | 617 | 1 | `4bc47755fddef646c4547091f4151b191258d0cf504f0a4de97738b8395c0108` |
| `snowcubes-18269cfd-contradiction` | contradiction | Snowcubes plan | 248,845 | 481 | 1 | `8c85ef19188c5e2d591404768e0ab77727a891cd4bf7701de2589f1aa7ce8e92` |
| `snowcubes-18269cfd-proof` | proof | Snowcubes plan | 248,845 | 650 | 1 | `14b5aee3871c2e9e5592d6fe10e75c45f7e714ceea20726c364524bcdbbe1e1e` |
| `snowcubes-18269cfd-history` | history | Snowcubes plan | 248,845 | 78 | 1 | `ad0b7723db3e98645171bd61da92b1718b8c66c66c9fa57e9aaf7c66c064f9fc` |
| `portfolio-owner` | owner | board + Shadow plan | 263,615 | 11 | 2 | `d26ca5e344bfa1cfdaa32b1d917bb3a6961d815c0edd67f072743195d3316c81` |
| `portfolio-current-work` | cross entity | board + all three plans | 761,701 | 241 | 4 | `cf1116c006a46e718bb63cd6256742aeab6a219b25d434576ac6615a233d5a63` |

The source names in the table abbreviate the exact refs and SHA-256 values in
**Frozen sources**. Snowcubes has no canonical `DECISION` Progress receipt in
this snapshot, so `snowcubes-18269cfd-decision` is excluded rather than given
an invented answer.

## Baseline distributions

Across the 16 answerable cases:

- source bytes: min 248,845; p50 249,241; p95/max 761,701;
- lookup hops: min 1; p50 1; p95/max 4;
- query p95 latency: min 0.502 ms; p50 0.794 ms; p95/max 2.857 ms;
- plan bytes: min 248,845; p50 249,241; p95/max 260,541.

The strongest leverage is not shaving a millisecond from regexes. It is making
the bytes loaded proportional to the requested milestone or receipt instead of
the entity's total hot history.

## External-source lead, not a decision

Nia indexed the official SQLite FTS5 documentation as source
`e6068626-7e16-4b83-8b00-396e57189c28` on 2026-08-13. Its external-content
contract separates canonical content from a search index, warns that drift
produces inconsistent results, and provides a full rebuild from canonical
content. That supports one candidate invariant for `~psc2`: an index may
accelerate discovery only if every returned row is re-read from current
source bytes and the whole index can be deleted and rebuilt. It does not prove
that SQLite, FTS5, or any persistent database is the smallest remedy.

Primary source: <https://www.sqlite.org/fts5.html>, especially sections 4.4.4
and 6.12.

## Gates for the next decision

`~psc2` must compare three layouts against this exact corpus:

1. monolith plus a disposable offset/search index;
2. bounded hot plan plus immutable archives and a manifest;
3. entity or milestone shards plus a manifest and disposable index.

No candidate advances unless it preserves every frozen result digest, refuses
stale source digests, retains one authority, gives atomic update and crash
recovery semantics, and reduces bytes loaded without making ordinary plan
editing or rollback depend on a service.

## Candidate comparison — 2026-08-13

The comparison model splits exact source bytes only at stable grammar
boundaries: sections, milestones, and append-only Deferred, Contradictions,
and Progress items. A JSON manifest orders every shard and binds its SHA-256,
byte length, section, tags, and referenced row IDs. Reassembling the ordered
shards must reproduce the original plan byte-for-byte. A stale digest refuses
before any row is returned.

The manifest is intentionally verbose in this experiment. It is a worst-case
inspectable routing surface, not a compressed target.

| Project | Candidate | Canonical + derived storage | Current lookup | Completion write | Exact reconstruction |
|---|---|---:|---:|---:|---|
| Shadow | monolith + offset index | 260,866 + 68,868 | 69,618 | 260,866 | yes |
| Shadow | hot plan + archives | 260,866 + 0 | 260,866 | 260,866 | yes |
| Shadow | manifest + shards | 329,734 + 0 | 69,618 | 70,130 | yes |
| Resplit | monolith + offset index | 249,241 + 53,814 | 64,002 | 249,241 | yes |
| Resplit | hot plan + archives | 249,241 + 0 | 249,241 | 249,241 | yes |
| Resplit | manifest + shards | 303,055 + 0 | 64,002 | 64,514 | yes |
| Snowcubes | monolith + offset index | 248,845 + 42,648 | 46,067 | 248,845 | yes |
| Snowcubes | hot plan + archives | 248,845 + 0 | 248,845 | 248,845 | yes |
| Snowcubes | manifest + shards | 291,493 + 0 | 46,067 | 46,579 | yes |

`Completion write` models one task-shard rewrite, one manifest rewrite, and
one new bounded receipt shard. Existing receipt shards are immutable. The
sharded candidate reduces current lookup bytes by 73.3%, 74.3%, and 81.5%, and
completion write amplification by 73.1%, 74.1%, and 81.3%, respectively. Its
tradeoff is 17.1–26.4% inspectable manifest overhead before compacting routing
metadata.

### Option 1 — monolith plus disposable index: rejected

This is the smallest read optimization. It preserves the current file and can
use `pread` offsets or FTS candidates followed by a current-source digest
check. It produces the same lookup-byte reduction as shards in the model.

It does not meet the full outcome. Every edit still atomically rewrites the
whole plan; every parser and mutator still needs a second indexed code path;
history growth still ends at the same hot-plan ceiling; and offsets invalidate
after ordinary edits. SQLite's official FTS5 warning applies directly: an
external index can disagree with content unless consistency is enforced. A
rebuildable index is useful later, but it cannot be the storage remedy.

### Option 2 — bounded hot plan plus immutable archives: keep as lifecycle, reject as architecture

Current `shadow lifecycle` already controls hot storage and is the safest
incremental migration tool. A dry run on completed M7 would reduce Shadow from
260,866 to 258,696 bytes and 117 to 113 rows. That is useful housekeeping.

It does not make active lookup proportional to the requested work. The parser
still reads the whole remaining hot plan, whose Progress section alone is
189,886 bytes. The field baseline also found four tombstones whose adjacent
machine-local archives are absent. Lifecycle remains part of migration and
retention, but tombstone-plus-file cannot be the only directory contract.

### Option 3 — manifest plus canonical shards: chosen

The entity remains one logical authority, but its bytes become one
content-addressed tree: a small manifest is the root locator and immutable or
atomically replaced shards own the exact content. The board continues to own
only project priority, entity pointer, claims, owner, and resume row. It never
copies task text or proof.

This is the only candidate that reduces both lookup bytes and write
amplification while scaling history independently of the active set. It also
preserves a zero-index fallback: scan and verify manifest entries, then parse
the same shards. A disposable index may accelerate routing, but deleting it
changes no answer or command semantic.

The design deliberately mirrors two primary-source invariants without copying
their implementations:

- Git's official object model uses content-addressed blobs plus trees that name
  and order them, allowing a complete snapshot to be reconstructed from
  immutable objects. Nia source `f5874419-96d2-4bc6-b3f9-a658bc7d9f47`.
- SQLite FTS5 external-content indexes can be discarded and rebuilt from
  canonical content; drift must refuse or be repaired, never silently answer.
  Nia source `e6068626-7e16-4b83-8b00-396e57189c28`.

Primary sources: <https://git-scm.com/book/en/v2/Git-Internals-Git-Objects>
and <https://www.sqlite.org/fts5.html>.

## Complexity decision

Let `M` be manifest bytes, `S` the selected shard bytes, `P` all canonical
entity bytes, and `E` the number of selected entities.

| Operation | Current monolith | Manifest + shards target |
|---|---:|---:|
| current row / proof / decision | `O(P)` time and loaded bytes | `O(M + S)` without index; `O(S)` after a digest-bound derived lookup |
| entity parse | `O(P)` | `O(M + sum(active shards))` |
| portfolio current work | `O(sum(P_e))` | `O(board + sum(M_e + S_e))` |
| task completion write | `O(P)` bytes | `O(M + task shard + new receipt shard)` |
| history growth | bounded by repeated monolith compaction | append immutable shards; active lookup independent of historical bytes |
| index loss | full scan of monolith | manifest scan; same source shards and answers |

The target is not theoretical constant time: a human-readable manifest is
linear in shard count. It is bounded-context routing whose cost grows with
structure metadata, not with every historical word. A later derived map may
make row-to-shard routing effectively constant-time, but the map stays
disposable.

## Failure modes the contract must close

1. **Manifest/shard mismatch:** refuse before returning content; never accept a
   tag or row map whose shard digest no longer matches.
2. **Half-written mutation:** publish new shards first, then atomically CAS the
   manifest; unreachable new shards are garbage, an old manifest remains valid.
3. **Missing shard:** refuse the entity as incomplete and retain the old
   manifest during recovery.
4. **Duplicate row ID across shards:** refuse the manifest and all mutating
   commands, just as the current plan refuses `ID-DUP`.
5. **Dangling `needs:` or Progress reference:** validate across the entire
   manifest tree before publish.
6. **Derived-index drift:** compare the indexed manifest digest; delete and
   rebuild on mismatch. Never return index text as authority.
7. **Concurrent writers:** one entity lifecycle lock and manifest CAS owns the
   transaction; a stale writer loses without overwriting a newer tree.
8. **Manual editing:** provide a deterministic materialize/edit/split workflow
   and keep the original monolith until the migration receipt proves exact
   reconstruction and rollback.
9. **Archive loss:** manifests bind every historical shard; a tombstone with no
   bound content is invalid rather than an optional broken link.
10. **Operator burden:** no daemon, service, credential, provider, or database
    is required. Python stdlib, JSON, files, SHA-256, atomic replace, and the
    existing lock/CAS owners are sufficient.

## Ruling

**Ponytail: keep — WORKS.** Keep the root board and entity identity; replace
the entity's monolithic payload with a manifest-addressed shard tree. This is
the first ladder rung that preserves exact authority while solving both read
and write scaling. Do not add SQLite, FTS, a service, or a persistent index to
the canonical path. Thermo classifies monolith-plus-index and archive-only as
follow-ups, not competing architectures.

## Normative plan-tree contract

This section is the `~psc3` contract. The words **MUST**, **MUST NOT**,
**SHOULD**, and **MAY** are normative. A plan tree is one logical authority,
not a directory of independent plans: the board still points to exactly one
`PLAN.md`, and only that root can publish a new generation.

### Authority and on-disk shape

`PLAN.md` MUST remain the stable entity locator. A migrated root contains a
short human-readable heading and one canonical JSON payload with schema
`shadow.plan-tree.v1`. The payload MUST contain:

- `generation`, a monotonically increasing non-negative integer;
- `logical_sha256` and `logical_bytes`, binding the exact materialized plan;
- `catalog_root`, `row_root`, and `tag_root`, each a SHA-256 object reference;
- `object_count`, `row_count`, and the checked-in format limits; and
- `previous_root`, the prior root digest or `null` for the first generation.

All referenced bytes live below
`PLAN.d/objects/sha256/<first-two-hex>/<full-sha256>`. Object names MUST equal
the SHA-256 of their bytes. Objects MUST be regular, non-symlink files beneath
the owning plan directory; readers MUST refuse path traversal, links, devices,
digest mismatch, malformed UTF-8, unsupported schemas, or an object larger
than its declared format limit. An object is immutable after publication.

The catalog is a bounded-page, content-addressed B+ tree keyed by a
zero-padded sequence number. A leaf value describes one canonical Markdown
shard: object digest, byte count, section, grammar-boundary kind, stable
logical ID, active/history state, row IDs, and receipt tags. The row tree maps
each globally unique `~id` to one catalog key. The tag tree maps
`<tag>/<timestamp>/<receipt-digest>` to one catalog key. Routing entries MAY
repeat locators and classifications, but MUST NOT copy task text, decisions,
proof text, or summaries. Every route MUST be revalidated against the selected
shard before an answer is returned.

Index pages MUST be at most 16 KiB, data shards at most 32 KiB, and the
`PLAN.md` root at most 8 KiB. Tree pages have at most 64 children. A single
grammar item that cannot fit a data shard MUST refuse migration rather than be
split mid-item. These budgets bound each stored object; the 256 KiB
logical ceiling still applies to the materialized hot plan, and active row
and milestone budgets remain unchanged. Historical growth adds immutable
shards and logarithmic catalog pages without enlarging the active context.

The three trees are canonical routing metadata inside the one plan authority.
They are not answer stores. A derived row, token, or full-text cache MAY exist
outside the plan directory only when it is keyed by the exact root digest,
contains no unique task state, can be deleted without changing an answer, and
rebuilds solely from verified tree objects. Cache mismatch MUST delete or
ignore the cache; it MUST never fall back to stale content.

### Losslessness and stable identity

Migration MUST split only before exact grammar boundaries: preamble, section,
milestone, and a top-level list item in any non-Tasks section, including append-only
Brief, Deferred, Contradictions, Progress, and legacy/custom receipt sections. Catalog
order plus shard bytes MUST reproduce the pre-migration `PLAN.md` byte for
byte, including final-newline state. The first root binds that original digest
and byte count. Later generations bind their own deterministic materialization.

Row IDs, milestone headings, `needs:` edges, DoD rows, archive references,
Progress timestamps, receipt tags, and receipt text MUST remain byte-identical
during migration. Stable logical shard IDs are format metadata and MUST NOT
replace row IDs. A milestone logical ID uses its earliest task-row ID; a
receipt uses its timestamp plus receipt digest; fixed sections use their
canonical section name. Renaming a heading therefore does not silently change
task identity.

Validation MUST materialize and parse the complete candidate generation before
publish. It MUST enforce every existing grammar and lifecycle invariant across
shards, including unique IDs, resolvable `needs:`, one DoD per milestone,
proof/decision reference integrity, chronological Progress, section order,
hot-row budgets, and archive availability. A tombstone without bound historical
content is invalid. The four missing Shadow archive targets found by `~psc1`
remain an explicit migration refusal until their authority is repaired; no
worktree copy may manufacture them.

### Lookup API and provenance

All Shadow commands MUST use one shared `PlanSnapshot` abstraction. It detects
a legacy monolith or a `shadow.plan-tree.v1` root and exposes the same logical
operations:

```text
materialize() -> exact logical PLAN bytes
row(~id) -> canonical task row and owning milestone
receipts(~id | tag, newest_first=True) -> canonical Progress items
section(name, active_only=False) -> canonical section items
provenance(result) -> root, index-page, shard, selector, and result digests
```

`status`, `throw`, `return`, `accept`, `amp`, `lint`, `lifecycle`, import, and
host verification MUST call this boundary rather than reading `PLAN.md`
directly. A legacy monolith remains supported during migration and returns a
single-source provenance receipt.

An exact row lookup traverses the row tree, one catalog path, and one data
shard. A tag lookup traverses the tag tree, one catalog path, and selected data
shards. At one million shards with fan-out 64, the acceptance budget is one
root, at most eight index pages across both trees, and one 32 KiB data shard:
at most ten file reads and 168 KiB of verified source bytes for a one-result
lookup. Result context is only the selected canonical item plus provenance.
Portfolio current-work lookup adds the board and one bounded lookup per entity;
it never materializes an entity merely to find its resume row.

Free-text discovery may consult a digest-bound disposable index, but the final
answer MUST re-read and verify every selected shard. With no cache, exact IDs,
tags, timestamps, and ordered history remain available from the tree. Search
results MUST say when they are discovery candidates rather than exact routes.

The public machine boundary for an already-migrated tree is `shadow read`.
Callers provide one full board-issued `--entity`, exact `--row` and zero-based
`--receipt TAG:N` selectors, and MAY bind the generation with `--expect-root`.
The board resolves the canonical pointer and rejects missing, stale, aliased, or
symlinked locators. One invocation is capped at eight selectors and 128 KiB of
selected result bytes. Selected canonical bytes are returned verbatim; private
plan pointer and error metadata are suppressed. It emits one JSON object only
after every selector verifies and the same entity pointer and root are re-read.
That final re-read is the projection's linearization point; later changes belong
to the next projection. A legacy monolith, missing/tampered object, changed root,
duplicate selector, or exceeded cap emits no partial content. It does not
materialize the plan or resolve archive tombstones and spill paths.

Every returned item carries: public entity locator, root digest, visited index
page digests, selected shard digest and byte count, selector, logical catalog
key, result byte range, and result digest. This is provenance—traceability to
canonical bytes—not telemetry, a summary, or a second status record.
`projection_sha256` hashes the canonical logical JSON object with that field
omitted; it does not hash the indented UTF-8 stdout representation.

### Mutation, concurrency, and recovery

One entity lock and root compare-and-swap own every mutation. A writer MUST:

1. freeze the board revision, claim, root state token, and current generation;
2. read and validate the current snapshot through `PlanSnapshot`;
3. write new data and index objects to same-filesystem temporary files, flush,
   verify their names and bytes, then atomically rename and fsync directories;
4. construct and fully validate the candidate root in memory;
5. atomically replace `PLAN.md` only if its frozen token still matches; and
6. update the board in its existing transaction only after the root publish
   succeeds, then re-read both root and board before reporting success.

An object written before the root is unreachable garbage and MAY be collected
after a grace period. A crash before root replacement leaves the old generation
authoritative. Atomic root replacement makes a half-root impossible. A missing
or corrupt referenced object makes the new root unreadable and MUST refuse all
semantic reads or mutations; recovery follows `previous_root` only through an
explicit rollback command, never as a silent answer fallback. A stale writer
loses the CAS without deleting another writer's objects.

Git-backed plans publish root and objects in one commit after focused
validation. Machine-local plans use the private Shadow journal and the same
root transaction. Merge, installation, deployment, and live-use receipts remain
separate from a green plan-tree test.

### Migration and rollback

`shadow plan migrate --dry-run` MUST be the first door. It reads one frozen
monolith, builds the complete candidate tree without publishing it, proves
byte-exact materialization, runs current lint and lifecycle validation, executes
the frozen query corpus against both layouts, and emits only public locators,
counts, budgets, and digests. It MUST perform zero writes to the plan, board, or
Git index.

Apply requires the dry-run root digest, the unchanged source token, a clean
owning checkout or private journal transaction, and no conflicting claim. The
board pointer and entity ID do not change. The migration commit or journal
receipt is the rollback bundle; ordinary reads never consult it as authority.

Rollback requires the expected current root digest. It restores the exact
pre-migration `PLAN.md`, validates its recorded digest and all board row/claim
references, publishes through the same CAS, and re-reads command outputs.
Unreachable objects are retained until rollback proof passes and only then may
be garbage-collected. Rollback MUST preserve every ID, receipt, pointer, claim,
owner, resume row, and command result from the frozen corpus.

### Mechanical acceptance

The architecture is complete only when all of the following are proven from a
clean checkout and a fresh seat:

1. the three real baseline plans and a generated million-shard fixture satisfy
   the page, hop, source-byte, and selected-context budgets;
2. all 16 frozen query result digests match before and after migration;
3. deleting every derived cache changes neither answer nor command behavior;
4. tamper, missing-object, duplicate-ID, dangling-edge, stale-CAS, concurrent
   writer, and crash-point fixtures refuse without publishing partial state;
5. `status`, `throw`, `return`, `accept`, `amp`, `lint`, `lifecycle`, import,
   and host verification have monolith/tree parity tests;
6. one machine-local Shadow plan and one representative product plan migrate,
   reopen from a cold seat, and return the expected active work, decision,
   contradiction, proof, and historical receipt with provenance;
7. both plans roll back byte-exactly and retain board pointers and claims; and
8. source, merged `origin/main`, installed executable, and live dogfood
   readbacks are recorded separately.

**Thermo:** the contract adds one shared snapshot boundary and one object-tree
format; it does not add a daemon, database, provider, alternate planner, or
per-command shard logic. **Ponytail: keep — WORKS.** This is the minimum remedy
that solves both monolith lookup and monolith write amplification while keeping
all current authority and safety invariants. The remaining proof gap is the
dry-run migration/query harness and command parity on real plans.

## First dry-run harness receipt — 2026-08-13

The first implementation slice now has one canonical splitter/tree builder,
an on-disk snapshot reader, bounded exact row/tag routing, source-byte
provenance, route rebuilding, and a strictly read-only migration CLI. It uses
only Python standard-library files, JSON, and SHA-256. There is no database,
daemon, cache, provider, or write-capable migration door.

The dry run freezes the plan and optional board bytes, validates all archive
links, rejects duplicate row IDs and dangling `needs:`, builds the candidate
entirely in memory, reconstructs the original bytes, rebuilds row/tag routes
from canonical shards, repeats every exact route, then re-reads both frozen
inputs. Its report declares `writes: 0` and contains no plan prose or private
path.

Observed against root-board revision 704:

| Entity | Result | Source bytes | Candidate root | Objects / bytes | Max data / index | Depth |
|---|---|---:|---|---:|---:|---:|
| Shadow | refused: bound archive content is missing | 259,494 | — | — | — | — |
| Resplit iOS | exact, routes rebuilt, zero writes | 249,241 | `71540f4bf71d` | 328 / 350,507 | 24,055 / 16,224 | 2 |
| Snowcubes | exact, routes rebuilt, zero writes | 248,845 | `279e4607e045` | 273 / 339,385 | 27,542 / 16,344 | 2 |

Resplit and Snowcubes materialized to their frozen source digests
`deb160f73da6…` and `1383b4e6854c…`. Shadow's refusal is correct: `~psc1`
found four tombstones whose machine-local archive bytes are absent. The
harness does not copy similarly named history from a worktree or weaken the
archive contract. That source repair remains required before Shadow can be
migrated.

The current exact lookup projection on the same real sources loads 95,280 to
127,679 verified bytes rather than 248,845 to 259,494 monolith bytes. This is a
first-source result, not M26 completion: atomic apply/rollback, all-command
parity, million-shard structure, two real migrations, cold-seat retrieval,
merge, install, and live readback remain open.

## Final real-plan and cold-seat receipt — 2026-08-13

`~psc5` migrated the machine-local Shadow authority and the registered
Snowcubes product authority through the public `shadow plan` door. In both
cases the board entity, pointer, owner, resume row, and live claims were frozen
before the operation and identical on readback. Neither migration copied task
text into the board or introduced a database, daemon, search service, or
derived cache.

| Authority | Pre-migration logical SHA-256 | Logical bytes | Rows | First tree root | Objects / object bytes | Max index / data | Depth |
|---|---|---:|---:|---|---:|---:|---:|
| machine-local Shadow | `23f111dd544f` | 260,002 | 113 | `fa63c6db592b` | 418 / 419,323 | 16,377 / 9,423 | 2 |
| Snowcubes product | `1383b4e6854c` | 248,845 | 136 | `fc43640eb581` | 276 / 355,284 | 16,364 / 27,542 | 2 |

The first Shadow apply published generation 1. Accepting `~psc5` later used
the same mutation boundary and advanced that live tree to generation 2; its
current root is `14d1cfdefe9c`, its exact logical payload is 260,167 bytes at
`c1b8959a740c`, and `previous_root` binds the accepted generation-1 root.
Snowcubes remains generation 1 at root `fc43640eb581`, with the exact original
logical digest `1383b4e6854c`.

### Rollback and immutable-object reuse

Both authorities were rolled back with an expected-root CAS. Shadow restored
the exact 260,002-byte monolith and source digest; Snowcubes restored the exact
248,845-byte monolith and source digest. Board revision, entity IDs, pointers,
resume rows, owners, and claims were byte-identical across each rollback. Each
authority was then migrated again to the same first-root digest. Because
objects are content addressed and retained until rollback proof passes, each
re-apply needed only the one new root publication; it did not rewrite the
existing shard set.

The Snowcubes Git receipts are deliberately separate:

- first apply: `0b3d9dab`;
- exact rollback: `eea144da`;
- same-root re-apply: `882e949`.

The machine-local Shadow operations are recorded in its private journal rather
than a product Git checkout. `shadow accept --row ~psc5 --by codex --no-push`
then passed its declared proof in a clean source checkout and advanced the root
board from revision 706 to 707 without leaving an orphan claim.

### Fresh cold-seat lookup

From root-board revision 708, the full logical benchmark and a separately
opened cold tree snapshot answered the same 11 cases for the two migrated
entities. Every case had the same selected-result SHA-256. No cache was built
or consulted; exact row and receipt routes came only from the verified root,
index pages, and selected canonical shard.

| Case | Hops | Verified source bytes | p95 |
|---|---:|---:|---:|
| Shadow current work | 6 | 23,503 | 0.581 ms |
| Shadow decision | 6 | 20,356 | 0.531 ms |
| Shadow contradiction | 6 | 25,138 | 0.560 ms |
| Shadow proof | 6 | 20,244 | 0.539 ms |
| Shadow history | 7 | 27,883 | 0.726 ms |
| Snowcubes current work | 6 | 28,613 | 0.618 ms |
| Snowcubes contradiction | 6 | 24,091 | 0.544 ms |
| Snowcubes proof | 6 | 14,922 | 0.502 ms |
| Snowcubes history | 6 | 23,988 | 0.691 ms |
| Portfolio owner | 7 | 26,577 | 0.858 ms |
| Portfolio current work, two entities | 13 | 55,190 | 1.443 ms |

Across all 11 cases, verified source bytes were 14,922–55,190, p50 was
24,091, selected-result context was at most 650 bytes, and p95 latency was at
most 1.443 ms. The portfolio case is the board plus one bounded lookup per
entity, so its 13 hops are the sum of two entity paths rather than a violation
of the one-result entity budget.

The original 16-case corpus was also replayed without changing the paused
Resplit authority. A read-only copy of its exact frozen
`deb160f73da6cf…` bytes was partitioned in a temporary directory, joined to
the two live trees through a temporary board, queried 101 times, and then
discarded. All 16 full-logical and cold-tree result-digest maps were identical,
with no missing case. A single-entity lookup used at most seven hops, 31,481
verified source bytes, and 1.011 ms p95; the three-entity portfolio lookup used
19 aggregate hops and 84,883 bytes. This is M26 fixture proof only: it neither
claims nor advances any Resplit checkpoint.

An FYI from a second seat identified a larger real corpus after that replay:
the machine-local Grafana consolidation plan is 527,947 bytes at source digest
`f2e72f1b6ab8…`. Its first zero-write dry run correctly refused because a
legacy/custom `CURRENT-STATE HEADER` was one 135,388-byte section. Inspection
showed that it already contained independent top-level Markdown receipts; the
splitter had simply recognized that boundary only in four modern section
names. The format now accepts top-level list-item boundaries in every
non-Tasks section, keeps indented continuations attached, and still refuses a
single item over 32 KiB.

The repeated dry run on the unchanged real plan reconstructed all 527,947
bytes at the exact source digest, with candidate root `236bdd142395…`, 538
objects / 686,915 object bytes, 20,604-byte maximum data shard, 16,375-byte
maximum index page, depth 2, no route mismatch, and zero writes. Its legacy
`## ROWS` syntax intentionally produces zero standard Shadow row routes, so
this receipt proves lossless storage scaling only; the 16-case modern-plan
replay above remains the task-query and provenance proof.

The checked-in structural model at one million shards has tree depth 4. An
exact one-result lookup reads one root, at most eight index pages, and one
32-KiB data shard: 10 reads, 172,032 verified bytes (168 KiB), and at most
32,768 selected-context bytes. Historical words may grow without changing
that bound; only logarithmic routing depth changes at the declared fan-out.

### Command behavior and delivery boundaries

The canonical tree contains no derived index to disable. Deleting a possible
future cache is therefore already the exercised configuration: full logical
reads and bounded cold reads agree without it. The declared `~psc6` command
suite passed 122 tests covering the plan store and `throw`, `return`, and
`accept` semantics. Earlier clean release-train proof passed 954 tests with one
skip; the final train is repeated after this receipt so later live-canary fixes
cannot borrow that older green.

Delivery states remain separate:

- **source:** feature branch `feat/plan-scale-20260812` contains the plan-tree
  implementation and this receipt;
- **merged origin/main:** not yet present; `origin/main` remains `be3a9e9`;
- **installed executable:** `~/.local/bin/shadow` resolves to this
  feature checkout, `shadow --version` reports 1.0.1, and `shadow doctor`
  reports 17/17 checks without a hard failure;
- **live dogfood:** the installed command migrated, rolled back, reopened, and
  mutated the actual machine-local Shadow plan, while `shadow status` read the
  partitioned Shadow and Snowcubes authorities at board revisions 706–708.

The implementation is therefore source-proven, installed, and locally
dogfooded, but it must not be described as merged or publicly released until
`origin/main` contains the source and that state is read back independently.
