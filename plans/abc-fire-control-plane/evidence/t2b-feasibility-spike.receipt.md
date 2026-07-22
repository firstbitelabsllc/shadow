# T-2b feasibility spike receipt — make-or-break #4

**Task:** T-2b / recognition-mission **R3**  
**Authority:** `plans/abc-fire-control-plane/PLAN.md`  
**Date:** 2026-07-22T00:48Z  
**Lane:** A only (did not claim T-2c / R4)  
**Branch:** `vidux/abc-fire-control-plane-design`  
**Question:** Can a **sub-second cheap model** generate ≤3 **mutually-distinct** options **AND** narrow/select?

**Golden dialogues:** `evidence/golden-dialogues-t2b.md`  
**Sibling (concurrent GLM-delegate samples):** `evidence/feasibility-spike/SPIKE-RECEIPT.md`

---

## 1. Method (agent-owned)

| Step | What |
|---|---|
| 1 | Prefer cheapest worker path: Z.ai GLM via raw chat API + `delegate` path (sibling seat) |
| 2 | Fallback when Z.ai unpaid: Anthropic Haiku + OpenAI o3-mini / gpt-5.3-chat |
| 3 | Fixed clarify **generate** (≤3 options JSON) then **narrow** (pick + lock / ready / FIRE sketch) |
| 4 | Wall-clock measure each call with `time.perf_counter` (full HTTP response body) |
| 5 | Haiku streaming TTFT measured separately (first `text_delta`) |
| 6 | Distinctness: pairwise Jaccard on `label+detail` tokens; pass &lt; 0.55 + labels unequal |
| 7 | Soft human gate: agent writes go/no-go; standing one-line veto for Leo |

**Not measured:** voice/STT, iOS UI, FIRE→Mac executor, durable IR persistence (T-2c).

### Provider status on this machine (2026-07-22)

| Provider | Status |
|---|---|
| Z.ai `api.z.ai` (`glm-4.5-air`, `glm-5-turbo`, …) | **HTTP 429 / insufficient balance** on direct path; sibling seat still got `delegate` glm-max/glm completions earlier (multi-second) |
| Anthropic `claude-haiku-4-5-20251001` | Live — primary cheap latency bench |
| OpenAI `o3-mini-2025-01-31`, `gpt-5.3-chat-latest` | Live (restricted model list) |
| Ollama local | Installed; **no models listed** |
| Delegate `--model local` | Retired (exit 3) |

---

## 2. Models used

| Role | Model | Why |
|---|---|---|
| Primary cheap latency | `claude-haiku-4-5-20251001` | Cheapest available live Anthropic lane; TTFT sub-second |
| Quality + FIRE sketch | `gpt-5.3-chat-latest` | Reliable ready=true + fire_packet_sketch |
| Fast-ish OpenAI | `o3-mini-2025-01-31` | Sub-second ping; flaky empty content on longer JSON in this run |
| Sibling quality proof | `glm-max` / `glm` via `delegate.sh` | Outcome-class dinner options + inventory-first narrow (`feasibility-spike/`) |

---

## 3. Latency samples (wall-clock complete JSON unless noted)

### 3a Direct API — generate + narrow (product-shaped prompts)

| Model | Scenario | Generate ms | Narrow ms | Combined ms | n opts | distinct | ready |
|---|---|---:|---:|---:|---:|---|---|
| claude-haiku-4-5 | nicole-menu-depth | **2136** | **2768** | 4904 | 3 | PASS | false (more refine) |
| claude-haiku-4-5 | car-leo-freeform | **1968** | **2413** | 4381 | 3 | PASS | false (more refine) |
| gpt-5.3-chat-latest | nicole-menu-depth | **2481** | **3781** | 6262 | 3 | PASS | **true** + FIRE sketch |
| gpt-5.3-chat-latest | car-leo-freeform | **3026** | **3292** | 6318 | 3 | PASS | **true** + FIRE sketch |
| o3-mini | nicole-menu-depth | 2359 | parse fail / empty | — | 2 (gen) | PASS gen | — |

**Strict sub-second (&lt;1000 ms complete response):** **FAIL** for generate and narrow on every successful run.

### 3b Haiku streaming TTFT (tight prompt, 3 trials × 2 scenarios)

| Metric | Value (ms) |
|---|---:|
| gen TTFT p50 | **554** |
| gen TTFT min / max | 469 / 718 |
| gen wall-clock p50 (non-stream complete) | **2575** |
| gen wall min / max | 2152 / 5549 |
| narrow wall p50 | **2368** |

**TTFT sub-second:** **PASS** on Haiku (all 6 trials &lt; 1s).  
**Complete-options sub-second:** **FAIL**.

### 3c Sibling GLM-via-delegate (quality, not sub-second)

| Run | Model | duration_s | Quality note |
|---|---|---:|---|
| G1 blank-box dinner generate | glm-max | ~10 | 3 distinct outcome classes |
| G1 narrow after A | glm | ~14 | stays inventory-first |

Source: `evidence/feasibility-spike/spike-receipt.json`.

### 3d Provider ping (trivial JSON `{"ok":true}`)

| Model | ms |
|---|---:|
| o3-mini | 914 |
| claude-haiku-4-5 | 885 |
| gpt-5.3-chat-latest | 2144 |
| glm-4.5-air (Z.ai) | 429 insufficient balance |

Trivial pings can look near-sub-second; **product-shaped option JSON is multi-second**.

---

## 4. Distinctness check

**Method:** pairwise Jaccard on tokenized `label + detail`; threshold **0.55**; labels must differ.

| Sample | Pairs (Jaccard) | Result |
|---|---|---|
| Haiku Nicole | 0.091, 0.091, 0.043 | **PASS** |
| Haiku car-Leo | 0.238, 0.130, 0.130 | **PASS** |
| gpt-5.3 Nicole | 0.053, 0.211, 0.050 | **PASS** |
| gpt-5.3 car-Leo | 0.250, 0.176, 0.176 | **PASS** |
| Sibling GLM G1 labels | fridge / takeout / 20-min recipe | **PASS** (outcome classes) |

**Narrow inheritance:** Haiku Nicole after `A + friendly tone` offered calendar-format / tone / scope — not synonym "website help". Sibling GLM narrow after inventory A stayed fridge/sheet-pan/leftover classes.

---

## 5. Go / no-go

| Gate | Result |
|---|---|
| ≤3 options | **GO** |
| Mutually distinct | **GO** (all scored successful runs) |
| Narrow / select (+ rider locks) | **GO** |
| FIRE sketch when ready | **GO** on gpt-5.3; Haiku more conservative (`ready=false` extra refine) |
| Sub-second **complete** cheap turn | **NO-GO** (~2–3 s generate; ~2–4 s narrow on Haiku/OpenAI; ~10 s+ GLM delegate) |
| Sub-second **TTFT** (progressive UI) | **GO** on Haiku (~0.5 s) |

### Product decision (agent-owned)

**PROCEED (conditional GO).**  
Make-or-break quality (distinct options + narrow) is proven on cheap/mid models. Strict sub-second **full** JSON is **not** proven on available cloud cheap paths today — treat as UX residual (stream TTFT + skeleton chips + optional on-device small model later), **not** an architecture kill. Design budget: **~2.5 s p50 generate / ~3 s p50 narrow** remote; stream first tokens under 1 s.

**Standing one-line veto for Leo:** *Veto PROCEED if hard sub-second complete options are required before any design-spec work.*

---

## 6. Architecture implications (for T-3, not implemented here)

1. Clarify worker stays **cheap, tool-less, JSON-only** — quality bar is met.
2. Do **not** gate the standalone-B architecture on remote sub-second wall-clock.
3. UI: optimistic skeleton / stream TTFT; never block FIRE purity on latency.
4. Preferred production cheap lane TBD after Z.ai balance restore; Haiku is a valid interim clarify brain.
5. IR v0 (T-2c) unblocked: `RouterDecisionTrace`-shaped belief node can assume 2–3 distinct options per turn.

---

## 7. Artifacts

| Path | Role |
|---|---|
| `evidence/golden-dialogues-t2b.md` | Required golden dialogues (Nicole + car-Leo) |
| `evidence/t2b-feasibility-spike.receipt.md` | This receipt |
| `evidence/feasibility-spike/*` | Sibling GLM-delegate runs + earlier golden G1–G5 |
| `/tmp/t2b-spike-raw.json` | Machine raw (not committed; regenerable) |
| `/tmp/t2b-spike-tight.json` | TTFT multi-sample raw (not committed) |

---

## 8. [METER] this lane only

| Metric | Count |
|---|---:|
| Live generate completions scored | 5 successful (+1 o3-mini partial) |
| Live narrow completions scored | 4 |
| Distinctness PASS rate (successful gens) | 5/5 |
| Sub-second complete gens | 0 |
| Sub-second TTFT trials | 6/6 |
| Files written (this seat) | 2 required + PLAN update |
| Tasks stolen (T-2c/T-3/Lane B/C) | 0 |
