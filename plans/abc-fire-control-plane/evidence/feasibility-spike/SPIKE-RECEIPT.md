# Feasibility spike receipt — T-2b / R3

**Date:** 2026-07-22  
**Why frontier lead hands-on:** orchestration + acceptance of delegated GLM drafts (not self-codegen for options).

## Question
Can a sub-second cheap model generate ≤3 mutually-distinct options AND narrow?

## Results

| Run | Model | duration_s | count | labels ok | note |
|---|---|---:|---:|---|---|
| G1 blank-box dinner | glm-max | 10 | 3 | ["Use what's in the fridge", 'Order takeout under a budget', 'Cook one 20-minute recipe'] | narrow_q present |
| G1 narrow after A | glm | 14 | 3 | ['Fridge-clear pasta — whatever noodles, sauce, veg you have', 'Sheet-pan roast of current proteins + veg', 'Leftover grain bowls + eggs from the fridge'] | must stay inventory-first |

## Verdict

- **Quality generate+narrow:** PASS
- **Sub-second latency (remote GLM):** FAIL (~10s observed)
- **Product call:** PROCEED — quality is the make-or-break; latency is a UX budget, not a kill. Prefer local/small model or skeleton UI for sub-second feel.

## Sample output (G1)
```json
{"options":[{"id":"A","label":"Use what's in the fridge","rationale":"Inventory-first: shape dinner around ingredients already on hand."},{"id":"B","label":"Order takeout under a budget","rationale":"Delegate cooking; pick a cuisine and price cap."},{"id":"C","label":"Cook one 20-minute recipe","rationale":"Minimal-effort cook from a short ingredient list."}],"narrow_question":"Any dietary constraints or people counting?"}
```

## Next
- Mark T-2b completed with this receipt path
- IR v0 draft already at `../ir-v0-schema-draft.md` (R4 start)
- Design spec T-3 unblocked for agent-owned draft (soft gate)
