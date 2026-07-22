# Kitchen IR + FireGate non-repo spike receipt

**Date:** 2026-07-22  
**Proof:** `swift test` in this package → **11 tests, 0 failures**

| Gate logic | Test |
|---|---|
| Rider on chosen (not 4th peer) | `testRiderAttachesToChosenNotPeer` |
| Disk resume G5 | `testDiskResumeRestoresSession` |
| Distinctness G1 helper | `testDistinctnessRejectsSynonymSpam` |
| Dry-run before high-blast seal G6 | `testDryRunRequiredBeforeHighBlastSeal` |
| Wrong confirm word | `testWrongConfirmWordRejects` |
| Abort → no packet / no executor G4 | `testAbortAfterDryRunNoPacketNoExecutor` |
| Seal packet fields G3 | `testG3SealWritesImmutablePacketFields` |
| Offline Nicole golden (T-2b lift) | `testNicoleMenuFixtureDistinctAndChoose` |
| Offline Car-Leo golden (T-2b lift) | `testCarLeoFixtureDistinctAndChoose` |
| Synonym spam negative control | `testSynonymFailNegativeControl` |

**Fixtures (offline, no model spend):**
- `Fixtures/d-nicole-menu.json` — D-Nicole menu-depth from `golden-dialogues-t2b.md`
- `Fixtures/d-carleo-freeform.json` — D-CarLeo freeform from same
- `Fixtures/synonym-fail.json` — negative control for Distinctness

**Hard rail held:** no `gh repo create`, no app target, no signing, **no push to public `firstbitelabsllc/vidux`**.
