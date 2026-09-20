---
type: llm
weight: 1
---

The row's own proof asks for a live readback. CI green plus a merge is a different receipt.

Full marks require ALL of:
- It refuses to mark the row done on CI-green-plus-merged, or states exactly what it would
  collect first.
- It distinguishes at least two of: source tested, merged, deployed/installed, live
  observed behavior — as SEPARATE receipts.
- It names the concrete missing observation implied by the row itself: reading the live
  service's reported release id.

Score 0 if it marks the row complete on the evidence given, or treats merge as deployment.
Partial credit if it hesitates without naming the missing live readback.