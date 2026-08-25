# Amplify — a loose steer into an executable goal

A person mid-work does not speak in briefs. They say *"use adversaries, or dial
in jordan mode / focus on details, yadi yadia"* — and that sentence carries
three real mechanisms plus filler. Amplifying is not making prose prettier. It
is **translating intent into mechanism, then deleting everything that does not
change what an agent does.**

Read this when the request is a steer rather than a task. The method and the
output shape live in `../SKILL.md`; this page is the translation and the
formatting law.

## 1. Extract the mechanisms, drop the filler

Every loose steer is a mix of signal, emphasis, and noise. Split it before
writing anything.

| The steer says | It means, mechanically |
|---|---|
| "use adversaries", "challenge it", "try to break it" | Independent verifiers prompted to **refute**, not confirm; a finding dies unless it survives. Give each a distinct lens when the thing can fail more than one way. |
| "jordan mode", "take over", "don't ask" | Decide and execute in the same turn. No option menus. Exhaust the reachable queue before reporting idle. Only hard rails pause. |
| "focus on details", "be precise" | Every claim carries `file:line` or quoted command output. No "looks fine". Absence needs positive proof. |
| "fan out", "team agents" | Parallel work over **disjoint** surfaces, each with its own proof; never two writers on one row. |
| "use the cheaper models", "delegate out", "grok/cursor/sol it" | Route by cost, not habit: bulk build/proof/research/drafts go to GLM, Luna (exact spec), Terra, Grok, or Cursor through the delegate harness; Sol specs; Fable only for the hardest planning and challenge. The lead orchestrates and verifies; it does not type the bulk itself. Every delegated slice returns a receipt the lead re-proves. |
| "make it 3x shorter" | Delete duplication first, then hedges, then adjectives. Never delete a fact to hit a number — say so if the number forces one. |
| "ship it", "just do it" | Land it: commit, push, open the PR. "Done" means proven, not written. |
| "idk", "u decide" | The call is yours. State it in one line and proceed revertable. |
| "1000x better" | The current thing is the wrong *shape*, not underweight. Change the shape; do not add words. |
| "yadi yadia", "whatever", "etc" | Filler. Delete. It marks where the speaker stopped caring, not a requirement. |

**The filler test.** For each phrase ask: *if I deleted this, would any agent
behave differently?* If no, it is emphasis — drop it and keep the mechanism.

## 2. Bind every mechanism to something refusable

A mechanism with no gate is a mood. Give each one a proof that can fail.

```
"use adversaries"   → 3 refuters, each with its own lens; ≥2 refute = the finding dies
"focus on details"  → every finding quotes file:line; a claim without one is dropped
"3x shorter"        → 112 lines → ≤40, with no fact removed (diff shows only cuts)
```

If a mechanism cannot be bound to a check, name it as taste and say who judges
it. Unbound taste is legitimate; unbound taste *pretending* to be a gate is not.

## 3. Format for the reader that will execute it

An LLM reads a goal as a set of constraints, not a narrative. Shape it so the
constraint arrives before the elaboration.

- **Imperative, present tense.** "Read X, then Y" — not "the agent should
  consider reading X".
- **Front-load the refusal.** What must NOT happen goes early and absolute:
  *never force-push; never touch another lane's row.* Buried prohibitions are
  prohibitions that get skipped.
- **Atomic constraints per line.** A line holding unrelated constraints gets
  half-followed; parallel outcome lanes still belong in the same goal.
- **Table over prose** for anything with more than three parallel cases.
- **Name the artifact, not the intent.** "Append a row to `PLAN.md`" beats
  "track the work".
- **Quote the person verbatim** where their words are the authority — a steer
  paraphrased is a steer weakened, and the quote is what settles later disputes.
- **State the ref.** Every authority is `repo + path @ ref`; a goal that says
  "the plan" without a ref invites a stale read.
- **Say what is already true.** Context the executor would otherwise re-derive
  (what was tried, what was refuted) is the cheapest thing in the prompt and
  the most expensive thing to rediscover.
- **End on the acceptance behavior**, stated so it is mechanically checkable.

## 4. Cut, in this order

1. Duplicate policy already in `AGENT.md`, `SKILL.md`, or the repo's own
   instructions — pointing beats restating, and restating drifts.
2. Invented vocabulary: phase names, track numbers, plan slugs, tier jargon.
   Standard words only.
3. Recurrence instructions ("check every 30 minutes") — Shadow has no
   scheduler; recurrence lives outside it.
4. Hedges: "try to", "if possible", "consider", "ideally". Either it is
   required or it is not in the goal.
5. Adjectives that carry no constraint: "robust", "comprehensive", "seamless".
6. Anything the executor can read for itself in one command.

## 5. The gate before you hand it over

- A fresh session could execute it without asking what anything means.
- Every line changes an implementation or a safety decision.
- `done`, `merged`, `live`, and `proven` stay distinct words.
- Every mechanism has a refusable proof, or is labelled taste with a judge.
- The brief is **shorter than the context it replaces**. If it is longer, the
  extraction failed — go back to step 1.
- The one standing Shadow goal stays unchanged and skill-free. A specific
  launcher is normally four lines and at most 80 words, ending with one to four
  canonical local skill names. Durable detail and the full roster belong in
  `PLAN.md`, not a longer prompt.

## Worked example

**Steer:** *"use adversaries, or dial in jordan mode / focus on details, yadi
yadia — in no way is this close to the actual prompt i want but you get the
spirit."*

**Extract:** adversarial verification · take-over autonomy · file:line
precision. `yadi yadia` and the disclaimer are filler — they say "I trust you
to finish the thought", which is itself the autonomy mechanism, already
captured.

**Amplified:**

```text
Outcome: every finding in <scope> is either proven with file:line or dead.
Resume: shadow status --by <seat> + ~/.shadow/plans/<entity>/PLAN.md at committed ref; continue owned claims, then the highest-value reachable checkpoint; delegate refuters to the cheaper roster when a harness is installed, else native.
Proof: each finding gets correctness, security, and reproduction refuters; two refutations kill it. Survivors require file:line or command evidence, <focused command> green, and <real surface> re-observed from fresh state.
Skills: thermo, ponytail.
```

Three mechanisms, each bound to a refusal, plus the two locally available
skills that execute the refutation. Nothing decorative. That is the whole move.
