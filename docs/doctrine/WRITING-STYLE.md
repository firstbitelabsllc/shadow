# Vidux Writing Style — say less

Spend the prompt budget on testable directives. Delete prose that does not
change behavior. This document is a model of its own rules.

---

## 1. State the rule. Don't narrate it.

Drop "Why this exists / Why this matters" framing. Keep a claim only when its
evidence is public, reproducible, and relevant.

<bad>
`PLAN.md` is the queue, decision, constraint, progress, and proof-reference
authority. Code derives from that plan state.
</bad>

<good>
`PLAN.md` owns work, decisions, constraints, progress, and proof references.
Code derives from it.
</good>

Private anecdotes and unsupported metrics are decoration — cut them.

---

## 2. Every line must be true/false testable

Replace mood lines with falsifiable directives an agent can check against.

<bad>
Silence is not confirmation. Be hungry for steering. The whole point is anticipating what needs to happen next.
</bad>

<good>
No assigned task != no work: scan the plan, read evidence, check what changed. Brief the human — what happened, options, your pick — then "steer me."
</good>

<bad>
If you are coding more than planning, stop. Front-load thinking.
</bad>

<good>
Name the outcome and acceptance check before implementation.
</good>

---

## 3. Define repeated phrases ONCE as a named term

If a field list repeats, name it once and reference it.

<bad>
...pair the shipped change with a checkpoint.
</bad>

<good>
checkpoint = {outcome, revision, proof, risk, resume}

...ship the change and record the checkpoint in the owning plan.
</good>

---

## 4. Tables/lists beat prose for enumerable content

Parallel prose paragraphs ARE a table. Same shape repeated N times = N rows.

<bad>
**1. Brainstorm-Plan-Execute-Verify Chain. What it does.** Enforces a strict phase sequence... **How Vidux adopts it.** ... **What we do NOT adopt.** Superpowers' brainstorm phase is interactive...
</bad>

<good>
| Pattern | Source | Adopt | Skip |
|---|---|---|---|
| Brainstorm->Plan->Execute->Verify | superpowers (128K) | plan-as-gate (LOOP Step 3) | interactive brainstorm; skill-per-phase |
</good>

But don't inflate ONE sentence into a multi-column band. Prose for one claim; table for many.

---

## 5. Reference, don't paste

Point to a canonical file/script. Never render the same content twice in two formats.

<bad>
### Configuration
{hook JSON with prompt text}

### What gets injected
> CHECKPOINT: Record outcome, revision, proof, risk, and one resume action.
</bad>

<good>
Reference the canonical checkpoint definition rather than copying it.
</good>

Remove private incident narratives from the kernel doc:

<bad>
An internal incident narrative with machine paths and timestamps.
</bad>

<good>
Verify the served artifact through the public boundary; a local filesystem entry
alone is not proof.
</good>

---

## 6. One concept per chunk

Welded mega-paragraphs hide rules. Split 4 rules into 4 bullets.

<bad>
Prove it mechanically: hit the live surface not the merge, and spot-check one entry per audit category, and every failure gets a code fix and a process fix, and a wiring PR... {354 words, 4 rules}
</bad>

<good>
Prove it mechanically:
- Hit the live surface, not the merge.
- Spot-check 1 entry per audit category.
- Every failure -> code fix + process fix.
- Wiring a pending path: activate its skipped tests or delete them. No stale skips.
</good>

---

## 7. Lead with the hard gate. Repeat it at the foot.

U-shaped attention: the start and end of a file get read. Don't bury a NEVER mid-paragraph.

<bad>
Prereqs: clone the repo. Verify: resolve the repo-relative plan path. Safety:
do not create duplicate plans, delete worktrees, or push/merge without authority.
</bad>

<good>
NEVER: duplicate plans, delete worktrees, or push/merge unless the owning plan
and authorization make it explicit.
Prereqs: clone the repo, install its documented toolchain, and read
`AGENTS.md` plus `PLAN.md`.
Verify: resolve plan path, inspect git state, run the smallest repo-owned proof.
</good>

---

## 8. One name per concept

The core loop has FOUR names across four files. Pick one 5-verb spine.

<bad>
Gather->Plan->Execute->Verify->Checkpoint (DOCTRINE)
READ->ASSESS->ACT->VERIFY->CHECKPOINT (SKILL)
Orient->Choose->Execute->Handoff (Harness Contract)
Read->Assess->Act->Checkpoint->Complete (LOOP)
</bad>

<good>
READ -> ASSESS -> ACT -> VERIFY -> CHECKPOINT (canonical, defined in LOOP.md; every other file links it).
</good>

---

## 9. Grep-and-kill list

These cost budget and drive no behavior. Find them, rewrite to a rule or delete.

<bad>
try to / be hungry for / crystal clear / the whole point / masquerading as / It's worth naming / two seams worth naming / The canonical failure this prevents / Despite having only N stars / This is the single rule that / wearing a lab coat / a parked car with the engine running / dramatic / genuinely / honestly / badly stale / pure overhead
</bad>

<good>
Keep ONE memorable metaphor if it earns its line. Delete the rest. Prefer the bare imperative.
</good>

---

## 10. Entry formats (task / evidence / progress)

**Task:**
<bad>- [ ] We should probably go through and make sure the checkout flow properly handles the edge case where a user has an expired session, since this has caused problems before</bad>
<good>- [ ] Checkout: handle expired-session edge case. Evidence: prior 403 in #34238.</good>

**Evidence line:**
<bad>It's worth noting that based on my investigation the currency API actually returns integers and not ISO codes as one might assume.</bad>
<good>Evidence: currency API returns integers, not ISO codes (worker/fx.ts:42).</good>

**Progress entry:**
<bad>I went ahead and made good progress on the reviews widget — got it mostly wired up and it's looking pretty solid, will pick up the remaining bits next session.</bad>
<good>Progress: reviews widget wired to the backend. Done: render + submit.
Next: verification gate. Files: reviews-widget.js, worker/reviews.ts.</good>

---

## The mandate

Vidux's §Voice & Tone says "terse, concrete, evidence-cited, no hedging." Hold the docs to it. Cutting prose RAISES compliance — shorter is more obeyed.
