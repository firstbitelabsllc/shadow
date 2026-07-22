I'll do a read-only planning pass: load the authority plans and memory, then return a sharp design draft with no edits or invented runtime proof.Living plan is under the repo; reading it plus related design evidence.# ABC → FIRE Control Plane — Planning Draft

**Authority read:** repo `PLAN.md` (1.0.0 thin layer), living design plan `plans/abc-fire-control-plane/PLAN.md` (external store is tombstone → same file), memories `vidux-repurpose-intent-2026-07-20` + `moussey-killed-adopt-verdict`. **Ref:** `vidux-main-active` @ `d5e89a49` on branch `vidux/abc-fire-control-plane-design`. Prior Fable invoke receipted as error (usage credits / exit 127); this draft is the advisor pass only — no live host/RC proof claimed.

---

## 1. Verdict

**Provisional Option A is the right home**, with one hard boundary: Vidux becomes the **ABC→FIRE control-plane product** (session contract, durable choice ledger, sealed FIRE handoff, plan/proof/resume), **not** a rebuilt mobile agent, voice stack, or model router. That fits the clean 1.0 shell (plan authority, steering mailbox already non-executing, browse as cockpit projection, host owns runners) and the no-new-repo rule.  
**Reject Option B** (“leave Vidux frozen; only a Claude skill/prompt”) — Nicole’s barrier is blank freeform + no durable recovery; a chat-only skill dies with the session and reintroduces essay mode under a different name.  
**Reject Option C** (“new app / Paseo-first product surface”) — September repo freeze, moussey-kill adopt order (Claude iOS + Remote Control first, Paseo trial second), and bus-factor/security tax make a greenfield mobile product wrong for v1.  
Standing veto for Leo stands: product-direction fork remains human-gated.

---

## 2. Problem statement

Nicole does not fail at *using* AI — she fails at **authoring the prompt**. A blank box is a freeform SAT essay; she needs multiple choice that still allows “A and also…”. Leo’s on-the-go need is the same loop under constraints (driving, cmux handoff): rough intent → cheap clarify → **CONTINUE** or **FIRE** → Mac/host agency — without typing a desktop coding session on a phone. Until FIRE, nothing expensive or mutating should run; after FIRE, durability and resume must outlive the chat.

---

## 3. Non-goals for v1

- Desktop chat UX ported to mobile as the product
- Rebuilding moussey / Pipecat / LiveKit / DIY voice runtime
- Voice car mode as first ship
- Synthetic-voice / fake-mic test harness for StrongYes (lesson only)
- Vidux owning model routing, provider transport, or worker execution (Pilot / host)
- Fixing Delegate GLM/Grok routing before design (explicit non-blocker)
- New repo or new iOS app before September 2026
- Expensive multi-agent coding work before FIRE
- “Unpause” old plan-first fleet orchestration (different veto; not this product)
- OpenClaw / Funnel / broad Slack+voice platform in v1

---

## 4. Three approaches

| | Approach | Trade-offs |
|---|---|---|
| **★ Rec** | **A — Vidux *is* the control plane**  
Repurpose 1.0 into ABC→FIRE: durable session schema, CONTINUE/FIRE semantics, plan-bound handoff packet; mobile surface = Claude iOS voice + Remote Control first; Paseo only if RC gap is proven. | **+** No new repo; reuses plan/proof/resume + non-executing steering; Nicole wedge owns a home; Leo veto is clear.  
**−** Root 1.0 public story (“thin layer only”) must be consciously rewritten after Leo lock; risk of scope-creep into “mini-host” if FIRE boundary is soft. |
| | **B — Skill/prompt only on coding host**  
Ship ABC→FIRE as Claude project skill / system prompt; Vidux stays frozen 1.0 docs. | **+** Fastest demo; zero product fork.  
**−** Chat is authority again; no Nicole-safe resume; no sealed FIRE packet; fails “survive interruption” doctrine; not a product. |
| | **C — Paseo/UI-first product**  
Trial Paseo (or similar) as the mobile loop; Vidux remains backend notes. | **+** Real phone loop sooner for Leo voice.  
**−** Wrong adopt order vs moussey verdict; AGPL/bus-factor; still needs a durable control contract; delays Nicole text-first wedge; feels like moussey with different paint. |

**Recommendation: A.** Implementation order inside A: **contract + durable pre-FIRE state first**, Claude iOS/RC as interaction host, Paseo only on a named RC gap.

---

## 5. Minimal architecture

**Components (v1)**

1. **Intent session** — one active session object: rough intent, clarifying turns, current A/B/C set, accumulated constraints, status (`clarifying` | `ready` | `fired` | `aborted`).
2. **Clarify worker (cheap)** — single LLM turn that *only* proposes A/B/C + optional short clarifying Q; no tools, no repo mutation, no Pilot dispatch.
3. **Vidux store** — session + choice history as plan-scoped durable state (session file / plan row + evidence); optional browse projection; steering mailbox remains transport for one-shot host intents, not execution.
4. **FIRE packet** — sealed, versioned handoff: goal outcome, locked choices, constraints, acceptance sketch, target plan path, resume id. Immutable after FIRE except abort.
5. **Coding host** — Claude Code Remote Control (primary) or later cmux/Pilot-selected runner; executes only after FIRE.
6. **Pilot** — worker routing *after* FIRE if multi-runner; not in the clarify loop.

**Data flow**

```text
OPEN intent ──► CLARIFY (cheap) ──► render A/B/C
                    ▲                    │
                    │    CONTINUE        │ pick A | A+delta | Q answer
                    └────────────────────┘
                              │
                            FIRE ──► FIRE packet ──► Host/RC (mutate/execute)
                              │
                            ABORT ──► session terminal; no host work
```

| Layer | Owns | Must not own |
|---|---|---|
| **Vidux** | Session schema, CONTINUE semantics, FIRE/ABORT gates, durable pre-FIRE ledger, post-FIRE plan/proof/resume binding | Model pick, tool execution, Tailscale daemon, voice stack |
| **Pilot** | Post-FIRE runner choice when needed | Pre-FIRE A/B/C content |
| **Host (Claude RC / later Paseo / cmux)** | Mac agency, tools, skills runtime, voice UI channel | Becoming the durable queue of truth |
| **Clarify LLM** | Options + questions only | File writes, shell, multi-step agent loops |

**Plumbing lesson (not rebuild):** Remote Control / Paseo teach local Mac reachability and skill attach; Vidux consumes that as **transport after FIRE**, never as a second control plane.

---

## 6. Interaction contract

Exact turn shapes (user-facing + system):

### Open intent
```text
USER:  <rough free text or voice transcript>
SYS:   session.status = clarifying
       session.intent = <normalized short restatement, non-executing>
       → one CLARIFY turn
```

### A/B/C render
```text
ASSISTANT:
  Restate: <one sentence>
  Choose one (or combine):
  A) <concrete action path>
  B) <concrete action path>
  C) <concrete action path>
  Q?) <optional one clarifying question, max 1>
  Actions: reply A|B|C | "A and also …" | CONTINUE | FIRE | ABORT
```
Rules: 2–3 options only; each option is a *decision*, not a paragraph prompt; no tool calls.

### “A and also…”
```text
USER:  A and also <delta>
SYS:   session.locked += {choice: A, delta}
       if under-specified → CLARIFY again with updated constraints
       if ready → offer CONTINUE (more refine) or FIRE
```

### CONTINUE
```text
USER:  CONTINUE
SYS:   no host dispatch
       CLARIFY with prior locks as hard constraints
       never widen scope without a new option that says so
```

### FIRE
```text
USER:  FIRE
SYS:   require session.ready (at least one locked choice OR explicit “FIRE as-is” after warn)
       emit FIRE packet {intent, locks, constraints, plan_path?, acceptance}
       session.status = fired
       hand off to host; only now allow expensive/mutating work
HOST:  acknowledge packet id; execute; write proof/resume back into Vidux plan authority
```

### Abort
```text
USER:  ABORT | never mind | cancel
SYS:   session.status = aborted
       no FIRE packet; no host work; durable record = aborted intent only
```

**Invariant:** Any turn that would open tools, edit files, spend paid coding context beyond one cheap clarify completion, or start Pilot workers **without** `session.status = fired` is a contract violation.

---

## 7. First vertical slice

**Ship:** One **text** loop (voice optional later) where Nicole completes **one real, low-risk agentic task** without authoring a freeform coding prompt.

**Suggested task (home/Snowcubes-shaped, not fleet ops):**  
e.g. “Change the about-page blurb on trysnowcubes.com to mention weekend pop-ups” — or any single-repo, reversible copy/content edit Leo already trusts — **not** “fix Resplit 2.0.”

**Slice stack (smallest):**
1. Session file + CLI or browse-visible state: open → A/B/C → lock → FIRE packet dump (JSON/md).
2. Clarify = one cheap model call or **scripted fixture options** for the first dogfood if model wiring is not ready (fixture proves UX; live clarify is gate 2).
3. FIRE = human or host paste of packet into Claude Code / RC session that already has Mac agency — **no new daemon**.
4. Host does the edit; Vidux plan row records proof + resume.

**Acceptance gates (all required):**

| # | Gate | Pass if |
|---|---|---|
| G1 | No freeform authoring | Nicole never types a multi-sentence “system prompt”; only rough intent + A/B/C / “and also” / FIRE |
| G2 | Pre-FIRE purity | Audit log / session journal shows zero host tool/mutate events before FIRE timestamp |
| G3 | FIRE packet completeness | Packet contains intent, locked choices, constraints, target repo/plan, acceptance one-liner |
| G4 | Real outcome | Named task lands with mechanical proof (diff + deploy/preview or file proof appropriate to task) |
| G5 | Interrupt resume | Kill mid-clarify; reopen; session restores locks; no re-essay |
| G6 | Abort safety | ABORT leaves no host side effects |

If G1–G2 fail, the product is still desktop chat. If G3–G4 fail, it is a toy wizard.

---

## 8. Concrete blockers / missing evidence

Falsifiable only:

1. **Leo product gate open** — Decision Log has provisional Option A only; root `PLAN.md` Purpose still describes thin OSS plan/proof/resume with no ABC→FIRE purpose rewrite. Missing: Leo one-line lock or veto in design plan Decision Log.
2. **RC handoff proof missing** — No receipt in `plans/abc-fire-control-plane/evidence/` that Claude iOS Remote Control can accept a structured FIRE packet (skill file, pasted packet, or deep link) and run Mac tools. Command-shaped gap: “complete one RC session from phone with packet id X → host receipt Y.”
3. **Clarify owner unset** — No written choice of clarify transport (Claude Max via RC vs local cheap model vs fixture-first). Missing decision row, not code.
4. **Nicole task not named** — No single dogfood task with repo path + acceptance command in the design plan Tasks.
5. **Authority path split** — `~/Development/vidux-projects/abc-fire-control-plane/PLAN.md` is a **tombstone**; living plan is `vidux-main-active/plans/abc-fire-control-plane/PLAN.md`. Risk of dual writes until parent freezes one path in Operator Brief.
6. **Prior Fable receipt is error** — `evidence/fable-plan.receipt.json` status `error`, worker_exit 127 / credits; not a design rejection, but evidence folder must not treat that file as a folded draft.
7. **1.0 mutation threat model** — Root Constraints ban new mutation/remote dispatch without threat model. FIRE handoff to RC needs an explicit “Vidux never dispatches; host pulls FIRE packet” row before any endpoint work (even if v1 is file-based pull).

---

## 9. Next parent action

**One question for Leo (product-direction fork — not agent-decided):**

> **Lock Option A as: “Vidux = ABC→FIRE control-plane product (session + FIRE packet + plan/proof); mobile UI = Claude iOS + Remote Control first; no new app/repo; voice car mode and fake-mic harness stay out of v1” — yes / veto / change the home?**

If silent default for the lead: treat **yes**, write that line into the design plan Decision Log (reversible), freeze authority path to `vidux-main-active/plans/abc-fire-control-plane/PLAN.md`, and name Nicole’s first dogfood task + G1–G6 as T-3 inputs — still no product code until that lock is recorded.

---

*End of planning draft. No files edited; no runtime claims beyond what’s on disk in authority paths and the failed Fable receipt.*
