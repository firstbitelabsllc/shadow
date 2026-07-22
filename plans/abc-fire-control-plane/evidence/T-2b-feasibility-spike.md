# T-2b — ABC→FIRE feasibility spike (make-or-break #4)

**Authority:** `plans/abc-fire-control-plane/PLAN.md`  
**Mission row:** recognition R3  
**Date drafted:** 2026-07-21  
**Live bench status:** **NOT RUN successfully** — protocol + gates only. Prior probe attempt failed before quality scoring (see §9).

**Question:** Can a sub-second cheap model generate ≤3 mutually-distinct options **AND** narrow on pick?

---

## 1. Problem statement + acceptance gates

### Problem

Nicole hits a blank-box barrier ("I don't know what to ask"). Car-Leo has rough freeform intent while hands-busy. Both need the same adaptive loop: rough intent → cheap clarify (A/B/C, optional rider) → narrow → **FIRE** only when the human commits. Until FIRE, nothing expensive or mutating runs.

If a cheap model cannot reliably produce short, mutually-distinct outcome classes and inherit constraints on the next turn, the product collapses into synonym menus or essay-length options — architecture (IR, two-brain, fire gate) is irrelevant.

### Spike acceptance gates (all required)

| ID | Gate | Pass |
|---|---|---|
| G-count | Option count | Exactly 2 or 3 offered options (plus optional rider on pick — rider is not a 4th peer) |
| G-distinct | Mutually distinct | Passes §4 rubric (≥2 of 3 raters / mechanical checklist: different **outcome class**) |
| G-length | Label budget | Each label ≤8 words; no multi-paragraph essay; optional one-line rationale OK |
| G-narrow | Narrowing | After pick (+ optional rider), next turn's options inherit locked constraints; no synonym reshuffle of the same class |
| G-latency | Latency | p50 clarify wall clock **<1000ms** stretch / **<2500ms** hard ceiling on first cheap lane (`glm` high). See §5. |
| G-dialogues | Golden set | ≥4 of 5 sketches in §3 produce passing options under the same prompt shape |

**Spike pass** = G-count ∧ G-distinct ∧ G-length ∧ G-narrow ∧ G-latency on ≥4/5 golden dialogues (one live micro-bench run set, receipted).  
**Spike fail** = any kill criterion in §6.

This document is **not** a product app, not IR implementation, not a new repo.

---

## 2. Prototype protocol (first cheap model / API)

### Try first

| Order | Lane | Why |
|---|---|---|
| **1st** | `delegate.sh --model glm` → OpenCode `zai/glm-5.2 --variant high` | Explicit fast/cheap clarify lane on this Mac; local Ollama/`--model local` is **retired** (delegate exit 3). Closest to "glm-high". |
| 2nd | Same prompt via `opencode run --pure --agent worker --model zai/glm-5.2 --variant high` timed directly | Isolates delegate sandbox/workspace overhead if wall clock blows the budget |
| 3rd (only if 1–2 fail quality, not latency) | `delegate.sh --model glm-max` once | Quality rescue; if only max passes distinctness, record that cheap clarify is **not** proven |

### Prompt shape (fixed for the spike)

Worker returns **JSON only**, no tools, no prose outside JSON:

```json
{
  "options": [
    {"id": "A", "label": "…", "outcome_class": "…"},
    {"id": "B", "label": "…", "outcome_class": "…"},
    {"id": "C", "label": "…", "outcome_class": "…"}
  ],
  "narrow_question": "optional one short clarifying Q or null"
}
```

Second turn (narrow): same schema, with `prior_choice`, `rider`, and `constraints[]` inlined in the task.

### What this spike measures

- Quality of options + narrowing under a fixed prompt
- Wall-clock latency of one clarify completion

### What this spike does **not** measure

- Voice / STT / TTS
- FIRE packet → Mac executor
- Durable IR / choice-path stack persistence
- iOS UI

---

## 3. Golden dialogue sketches

Canonical copies also live in `evidence/feasibility-spike/golden-dialogues.md`. Sketches below are the scoring set.

### D1 — Nicole blank-box (menu-depth)

**User:** I don't know what to ask. I just want help with dinner tonight.

**Pass options (outcome classes):**
- A: Use what's already in the fridge *(inventory-first)*
- B: Order takeout under a budget *(order-out)*
- C: Cook one simple 20-minute recipe *(cook-simple)*

**Fail (synonyms):** "Help me decide dinner" / "Figure out what to eat" / "Meal ideas"

**Narrow on A:** next options stay inventory-first (e.g. leftovers vs shop-missing vs freeze-thaw), not "dinner ideas" again.

### D2 — Nicole partial + rider

**User:** Something for me and Leo, not too heavy.

**Pass options:**
- A: Two light pasta bowls
- B: Big shared salad + protein
- C: Soup + bread night

**User:** A, and also no dairy.

**Narrow:** dairy-free pasta variants only; `no dairy` locked in constraints.

### D3 — Car-Leo freeform (hands-busy)

**User:** text Nicole I'll be 20 late and ask if she needs anything from the store

**Pass options (2 + freeform OK):**
- A: Draft iMessage (edit before send) — **no send without FIRE**
- B: Add calendar note only
- C: Say it your way *(dictation rider)*

**Narrow / FIRE:** dry-run packet only after distinct confirm word; spike stops at option quality + narrow question, does not send.

### D4 — Ambiguous work ask

**User:** Can you fix the app?

**Pass options (force outcome-class split):**
- A: Crash / error right now *(debug-now)*
- B: Visual / polish change *(ui-polish)*
- C: New feature request *(feature)*

**Fail:** three phrasings of "help with the app".

### D5 — Already-clear intent → ready fast

**User:** Open a draft PR on resplit-web that renames the Trip Link sheet title to "Shared trip" and nothing else.

**Pass options:**
- A: FIRE with that exact scope
- B: Also update empty-state copy
- C: Clarify which screen first

**Pass criterion:** A is clearly the sealed-scope path; model does not invent a 4th scope or essay.

---

## 4. Distinctness rubric ("mutually distinct")

Score each turn independently. **Pass** requires all of:

1. **Outcome-class test** — For every pair of options, a human can name a different *end state* or *next action family* (not just different wording). Record `outcome_class` slug per option; duplicates → fail.
2. **Synonym ban** — If swapping labels would not change what the system would do next, fail.
3. **Partition test** — The three (or two) classes should be roughly exclusive for the user's next commitment; overlapping "do dinner" buckets fail.
4. **Non-essay** — Labels ≤8 words; if the model dumps paragraphs into `label`, fail G-length (and usually G-distinct).
5. **Narrow inheritance** — On turn N+1, every offered option must be compatible with accumulated constraints; any option that violates a locked rider → fail G-narrow.

**Quick rater sheet (0/1 per check):**

| Dialogue | Count 2–3 | Distinct classes | ≤8 words | Narrow inherits | Notes |
|---|---|---|---|---|---|
| D1 | | | | | |
| D2 | | | | | |
| D3 | | | | | |
| D4 | | | | | |
| D5 | | | | | |

Need ≥4/5 rows all-1s (plus latency) for spike pass.

---

## 5. Latency budget table

| Stage | Target | Hard ceiling | Notes |
|---|---|---|---|
| Cheap clarify completion (wall, one turn) | p50 **<1000ms** | **<2500ms** | First lane = `glm` high; measure client wall clock |
| Prompt assemble + JSON parse | <50ms | <100ms | Local; should be noise |
| Narrow turn (2nd call, same model) | p50 <1000ms | <2500ms | Same budget as clarify |
| End-to-end two-turn (clarify + narrow) | p50 <2000ms | <5000ms | Excludes human think time |
| UI render of 3 chips (out of spike) | n/a | n/a | Do not build UI in this spike |

If p50 is 1000–2500ms but quality passes: **conditional pass** — document as remote-GLM acceptable; revisit local/edge later. If >2500ms p50: fail G-latency even if quality is good.

---

## 6. Kill criteria (spike fails → do not commit architecture)

Stop and rewrite the clarify strategy (fixture-first, scripted menus, or different model class) if **any**:

1. **Synonym collapse** — ≥2/5 dialogues fail G-distinct on two consecutive prompt revisions.
2. **Essay mode** — Model cannot stay ≤8-word labels without heavy post-truncation that destroys meaning.
3. **No narrow** — After pick+rider, next options ignore constraints in ≥2 dialogues.
4. **Latency wall** — p50 wall clock **>2500ms** on `glm` high across ≥5 timed runs (or opencode-direct equivalent).
5. **Only max works** — Distinctness/narrow only pass on `glm-max` / frontier, never on `glm` high → cheap clarify brain is unproven; do not bake "always cheap" into the design spec.

Standing veto: "fixtures forever" — if killed, design may still ship fixture menus for Nicole dogfood, but must not claim live cheap-model clarify.

---

## 7. Exact next command — live micro-bench

**Do not claim pass/fail until this (or equivalent) produces a receipt with scored JSON.**

From a shell where `delegate.sh` and `opencode` are on PATH. Workspace must be the real git tree (not a symlink escape — prior attempt died on allowed-context rules).

```bash
# --- T-2b live micro-bench (D1 clarify) ---
REPO="/Users/leokwan/Development/vidux-main-active"
EVID="$REPO/plans/abc-fire-control-plane/evidence/feasibility-spike"
mkdir -p "$EVID"
cd "$REPO"

# Regular file inside workspace (required by delegate allowed-path rules)
cat > "$EVID/prompt-d1.txt" <<'EOF'
You are a clarify worker. Reply with JSON only (no markdown fences).
Schema:
{"options":[{"id":"A","label":"string ≤8 words","outcome_class":"slug"},{"id":"B","label":"string ≤8 words","outcome_class":"slug"},{"id":"C","label":"string ≤8 words","outcome_class":"slug"}],"narrow_question":"string or null"}
Rules: exactly 2 or 3 options; mutually distinct outcome classes (not synonyms); labels ≤8 words; no tools.
User: I don't know what to ask. I just want help with dinner tonight.
EOF

OUT="$EVID/glm-d1.out"
RCPT="$EVID/glm-d1.receipt.json"
START=$(python3 -c 'import time; print(int(time.time()*1000))')

delegate.sh \
  --task "Read the inlined prompt file. Return only the JSON object the prompt requests." \
  --model glm \
  --allowed-path "$EVID/prompt-d1.txt" \
  --out "$OUT" \
  --receipt "$RCPT"

END=$(python3 -c 'import time; print(int(time.time()*1000))')
WALL=$((END-START))
python3 - <<PY
import json, pathlib
ev = pathlib.Path("$EVID")
timing = {
  "dialogue": "D1",
  "model": "glm (zai/glm-5.2 variant high)",
  "wall_ms": $WALL,
  "out": "$OUT",
  "receipt": "$RCPT",
  "scored": False,
  "note": "Score G-count/G-distinct/G-length by hand or small script against T-2b rubric; then run D2–D5 + one narrow turn."
}
(ev / "timing-d1.json").write_text(json.dumps(timing, indent=2) + "\n")
print(json.dumps(timing, indent=2))
PY

# Narrow turn (after human/agent picks A + optional rider) — same pattern with prompt-d1-narrow.txt
# Repeat for D2–D5; write scored table into this file under §9 Live results.
```

**If delegate fails on workspace/context:** fall back to timed opencode-direct with the same prompt text (no `--allowed-path`), still write `timing-d1.json` + stdout to `$EVID/`.

**Resume after live run:** append §9 with wall_ms, JSON excerpt, rubric scores; then mark T-2b completed in PLAN **only if** gates pass.

---

## 8. What NOT to build yet

- **No new repo** / no `gh repo create` / no public push (hard rail).
- **No IR implementation** — `evidence/ir-v0-schema-draft.md` may exist as a sketch; do not code `BeliefNode` / choice-path stack into an app until T-2b passes (T-2c).
- **No iOS/SwiftUI app shell**, no FIRE executor, no voice harness wiring.
- **No product UI** for chips, riders, or confirm words.
- **No Pilot/host routing changes** — model routing stays Pilot/delegate-owned; this spike only samples the cheap clarify lane.
- **No claiming provider health** without a live receipt in `$EVID/`.

After a **passing** live bench: proceed to T-2c (IR v0 lift) then T-3 design spec.

---

## 9. Prior attempt / live results

### Prior probe (2026-07-21 ~20:44) — incomplete

Artifacts under `evidence/feasibility-spike/`:

| File | Result |
|---|---|
| `glm-abc-probe.stderr` | `delegate: allowed context must be a regular non-symlink file inside the resolved workspace` |
| `timing.json` | `wall_ms: 371` — fail-fast path; `count_2_or_3` / `distinct_outcome_classes` left **null** |
| `opencode-direct.stderr` | worker banner only (`glm-5.2`); `opencode-direct.out` empty |
| `golden-dialogues.md` | Sketches only (folded into §3) |

**Verdict:** no measured successful clarify completion; latency and distinctness **unproven**. Do not treat 371ms as a model latency sample.

### Live results (fill after §7)

| Dialogue | wall_ms | Count | Distinct | ≤8w | Narrow | Receipt |
|---|---|---|---|---|---|---|
| D1 | — | — | — | — | — | — |
| D2 | — | — | — | — | — | — |
| D3 | — | — | — | — | — | — |
| D4 | — | — | — | — | — | — |
| D5 | — | — | — | — | — | — |

**Spike status:** `in_progress` — protocol ready; awaiting live micro-bench.
