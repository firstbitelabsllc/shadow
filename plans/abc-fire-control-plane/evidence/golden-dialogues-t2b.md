# Golden dialogues — T-2b / R3

**Authority:** `plans/abc-fire-control-plane/PLAN.md`  
**Mission row:** recognition R3  
**Date:** 2026-07-22  
**Purpose:** Fixed scoring dialogues for the make-or-break #4 spike — can a cheap model emit ≤3 mutually-distinct options **and** narrow/select.

Related sketches (dinner/blank-box set): `evidence/feasibility-spike/golden-dialogues.md`.  
This file is the **required Lane A deliverable path** and centers the two product poles: **Nicole menu-depth** and **car-Leo freeform**.

---

## Scoring rubric (mechanical)

| Check | Pass |
|---|---|
| Count | 2–3 options |
| Distinctness | pairwise Jaccard(token set of `label+detail`) **&lt; 0.55** AND labels not identical; qualitatively different **outcome classes** (not paraphrases) |
| Length | labels ≤8 words; detail ≤12 words preferred; no multi-paragraph essay |
| Narrow | after pick (+ optional rider), next turn inherits locks; no synonym reshuffle of same class |
| Ready / FIRE sketch | when intent is bounded + reversible, `ready=true` + fire-packet sketch; else more options |

---

## D-Nicole — menu-depth (Snowcubes website)

**Persona:** Nicole — does not know what to ask; needs multiple choice, not a blank essay box.

**User (rough intent):**
> I want to update our Snowcubes website but I don't know what to ask for. Maybe something about weekend pop-ups?

### Expected outcome classes (not required verbatim)

| ID | Outcome class | Example label |
|---|---|---|
| A | New schedule surface | Add pop-up event calendar / schedule page |
| B | Dedicated landing | Create pop-up landing page |
| C | Homepage promo only | Update homepage banner |

**Fail (synonym clones):** "Help with the website" / "Update the site" / "Change something about pop-ups".

### Live model sample — `claude-haiku-4-5-20251001` (2026-07-22)

**Generate wall-clock:** 2136 ms · **n=3** · **distinct PASS** (pairwise Jaccard 0.091 / 0.091 / 0.043)

```text
Restate: Clarify what website update you need for Snowcubes weekend pop-ups.
A) Add pop-up event calendar — Display weekend pop-up dates, times, locations on website
B) Create pop-up landing page — Dedicated page with details, photos, booking for each pop-up
C) Update homepage banner — Highlight current/upcoming weekend pop-ups above the fold
```

**User pick:** `A and also keep the tone friendly not salesy`

**Narrow sample (Haiku):** locked = combine(A + friendly tone); `ready=false`; next options stayed on calendar/format/scope — not synonym "website help":

```text
D) Calendar format & interactivity
E) Tone & copy style
F) Scope & integration
```

**Narrow sample (`gpt-5.3-chat-latest`):** same pick → `ready=true` + FIRE packet sketch:

```text
intent: Create a Snowcubes website page that lists weekend pop-up locations, dates, and hours in a clear, friendly tone
locks: Dedicated pop-up schedule page; Include locations, dates, hours; Tone: friendly, not salesy
acceptance: Page is live with upcoming weekend pop-ups listed, easy to scan on mobile, copy reads casual and inviting (not promotional)
```

### Dialogue script (product UX shape)

```text
NICOLE: I want to update our Snowcubes website but I don't know what to ask for.
        Maybe something about weekend pop-ups?
APP:    Restate: You want a website change about weekend pop-ups.
        A) Add a pop-up schedule page
        B) New pop-up landing page
        C) Homepage banner only
        [A and also…] [CONTINUE] [FIRE] [ABORT]
NICOLE: A and also keep the tone friendly not salesy
APP:    Locked: schedule page + friendly non-salesy tone.
        Ready? Or refine:
        D) Grid vs list calendar
        E) Where the schedule lives (nav / homepage link)
        F) Who updates dates each week
NICOLE: FIRE
APP:    → FIRE packet (no host work before this gate)
```

---

## D-CarLeo — freeform hands-busy (About blurb)

**Persona:** car-Leo — rough freeform intent, wants short chips, will FIRE when it looks right.

**User (rough intent):**
> while driving: fix the about page blurb on trysnowcubes, mention weekend pop-ups in Queens, keep it short, then I'll FIRE when it looks right

### Expected outcome classes

| ID | Outcome class | Example label |
|---|---|---|
| A | Length/shape: 1 sentence | Ultra-short blurb |
| B | Length/shape: 2 sentences + brand | Short + friendly |
| C | Length/shape: short paragraph | Info-focused |

Alternate valid split (interaction mode, not copy length): Draft-now / Dictate / Template — also PASS if mutually distinct.

### Live model sample — `gpt-5.3-chat-latest` (2026-07-22)

**Generate wall-clock:** 3026 ms · **n=3** · **distinct PASS** (Jaccard 0.25 / 0.176 / 0.176)

```text
Restate: Edit the About page blurb for TrySnowCubes with a mention of Queens weekend pop-ups
A) Ultra-short blurb — One sentence, includes Queens pop-ups mention
B) Short + friendly — Two sentences, brand vibe plus Queens pop-ups
C) Info-focused — Brief paragraph, adds Queens pop-ups and context
```

**User pick:** `B`

**Narrow:** `ready=true` · FIRE sketch:

```text
intent: Draft a short, friendly two-sentence About page blurb for trysnowcubes that mentions weekend pop-ups in Queens.
locks: Two sentences; Friendly brand voice; Include weekend pop-ups in Queens; Keep it concise
acceptance: Produces 2 clean sentences, natural and on-brand, explicitly mentions weekend pop-ups in Queens, no fluff, ready to paste.
```

### Live model sample — `claude-haiku-4-5-20251001` (mode-class options)

**Generate wall-clock:** 1968 ms · **n=3** · **distinct PASS** (Jaccard 0.238 / 0.13 / 0.13)

```text
A) Draft & review later — compose now; review when parked
B) Voice-dictate the text — you dictate; app formats
C) Suggest a template — propose short template; approve/tweak
```

**Pick B → narrow:** inherits voice-dictate; next options = dictate-now / wait-until-parked / refine-length (still not synonym reshuffle).

### Dialogue script (product UX shape)

```text
LEO:   Fix the about page blurb on trysnowcubes — mention weekend pop-ups in Queens —
       keep it short. I'll FIRE when it looks right.
APP:   Restate: Short About blurb + Queens weekend pop-ups.
       A) One sentence
       B) Two sentences, friendly
       C) Short paragraph
LEO:   B
APP:   Locked: two-sentence friendly blurb with Queens pop-ups.
       Ready to FIRE. [FIRE] [CONTINUE] [ABORT]
LEO:   FIRE
APP:   → FIRE packet to Mac executor (blast-radius confirm word on host)
```

---

## Supporting dialogues (from concurrent G1–G5 set)

Canonical dinner / iMessage / ambiguous-work sketches live in  
`evidence/feasibility-spike/golden-dialogues.md` (G1–G5).  
GLM delegate live samples for G1 dinner blank-box + inventory-first narrow are receipted there under `feasibility-spike/glm-abc-*.out`.

---

## Distinctness check method (used in this spike)

1. Concatenate each option's `label` + `detail` (or rationale).
2. Tokenize to lowercase alphanumerics.
3. Pairwise Jaccard similarity; **pass if every pair &lt; 0.55** and labels not equal.
4. Human/agent spot-check: different **outcome classes** (what changes in the world), not synonym rewrites.

Recorded pairwise scores for Nicole Haiku sample: **0.091 / 0.091 / 0.043** (clear pass).  
Car-Leo gpt-5.3 sample: **0.25 / 0.176 / 0.176** (pass).
