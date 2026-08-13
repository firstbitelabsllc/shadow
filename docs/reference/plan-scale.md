# Plan scale — frozen baseline and decision gates

Status: **M26 baseline frozen; architecture not yet chosen.**

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

| Source | SHA-256 | Bytes | Rows | Milestones | Progress | Contradictions | Archives |
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

