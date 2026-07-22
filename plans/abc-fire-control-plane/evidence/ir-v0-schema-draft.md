# IR v0 schema draft — belief node + choice-path stack

**Source lift:** `moussey/lib/intent-router.ts` `RouterDecisionOption` / `RouterDecisionTrace`  
**Date:** 2026-07-22  
**Status:** agent-owned draft for review (soft gate rewritten — not human-sign-off)

## Lift map

| Moussey (routing) | ABC→FIRE (recognition) |
|---|---|
| `RouterDecisionOption.id/label/reason` | Option card id / short label / why-this-path |
| `status: selected \| rejected` | `status: offered \| chosen \| discarded \| rider` |
| `considered[]` / `rejected[]` | Full choice-path stack (ordered) |
| `latencyBudgetMs` | Clarify turn budget (spike target: <1000ms) |
| `classification` / `routeMode` | `clarifyMode: menu \| freeform \| hybrid` |

## Proposed types (TypeScript sketch)

```ts
export type ClarifyMode = "menu" | "freeform" | "hybrid";

export type ChoiceStatus = "offered" | "chosen" | "discarded" | "rider";

/** One A/B/C (or freeform) option at a turn. */
export type BeliefOption = {
  id: string;                 // stable within turn, e.g. "A" | "B" | "C" | "rider"
  label: string;              // ≤8 words, mutually distinct from siblings
  rationale: string;          // one sentence why this path
  status: ChoiceStatus;
  /** Freeform delta the human added when picking (Nicole "A and also…"). */
  riderText?: string;
};

/** Per-question belief node — one clarify turn. */
export type BeliefNode = {
  turnId: string;
  prompt: string;             // what the system asked / framed
  mode: ClarifyMode;
  latencyBudgetMs: number;
  latencyActualMs?: number;
  options: BeliefOption[];    // ≤3 offered (+ optional rider slot)
  selected?: BeliefOption;
  considered: BeliefOption[];
  discarded: BeliefOption[];
};

/** Editable choice-path stack across the session (pre-FIRE). */
export type ChoicePathStack = {
  sessionId: string;
  roughIntent: string;
  status: "clarifying" | "ready" | "fired" | "aborted";
  nodes: BeliefNode[];        // ordered history; last = current
  constraints: string[];      // accumulated riders + locked facts
  firePacketId?: string;
};
```

## Design rules (from spike intent)

1. ≤3 mutually-distinct options per turn (plus optional rider on pick).
2. Options must differ in *outcome class*, not synonym labels.
3. Stack is editable: human can discard a past node and re-clarify.
4. FIRE freezes stack → sealed packet; no mutation after FIRE except abort.

## Open review questions (agent-decided defaults)

- **Default:** rider attaches to chosen option, not a 4th peer option. Veto: "rider is peer".
- **Default:** menu-depth for Nicole starts with 3 concrete outcomes; freeform car-Leo may return 2 + "say it your way". Veto: "always 3".
- **Default:** IR lives in app session store first; Vidux plan/proof only after FIRE. Veto: "every turn in Vidux".

## Next

- Fold after T-2b spike receipt (latency + distinctness proof).
- Spec T-3 consumes this schema + two-brain split + fire gate.
