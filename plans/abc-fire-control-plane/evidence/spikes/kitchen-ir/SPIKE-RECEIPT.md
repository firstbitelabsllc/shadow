# Kitchen IR + FireGate non-repo spike receipt

**Date:** 2026-07-22  
**Proof:** `swift test` in this package → **8 tests, 0 failures**

| Gate logic | Test |
|---|---|
| Rider on chosen (not 4th peer) | `testRiderAttachesToChosenNotPeer` |
| Disk resume G5 | `testDiskResumeRestoresSession` |
| Distinctness G1 helper | `testDistinctnessRejectsSynonymSpam` |
| Dry-run before high-blast seal G6 | `testDryRunRequiredBeforeHighBlastSeal` |
| Wrong confirm word | `testWrongConfirmWordRejects` |
| Abort → no packet / no executor G4 | `testAbortAfterDryRunNoPacketNoExecutor` |
| Seal packet fields G3 | `testG3SealWritesImmutablePacketFields` |

**Hard rail held:** no `gh repo create`, no app target, no signing.
