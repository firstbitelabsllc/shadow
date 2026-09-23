# Eval suite — does this skill change what the agent does?

Seven cases, run by `claude plugin eval` with its no-plugin baseline arm:

```bash
claude plugin eval . --trust-plugin --runs 3 --no-publish
```

Each case pastes its own board state into the prompt. That is deliberate: the
eval sandbox is an empty workspace with no board, no shell and no write tools,
so a case that expects to *read* real state measures the sandbox instead of the
skill. The first run of this suite scored 0.00 in BOTH arms on all five cases
for exactly that reason — every grader's evidence quoted the agent saying the
working directory was empty. A 0 percent reading indicts the instrument first.

The cases are behavioral, not trivia:

| case | what it refuses to reward |
| --- | --- |
| `resume-cold` | handing the choice back: asking which project to pick when the board already answers it |
| `no-second-queue` | standing up a second tracker beside the plan that already holds work state |
| `proof-is-not-a-green-build` | treating CI green plus a merge as a deployment receipt |
| `park-with-one-wake` | parking a whole row when its blocker belongs to one action, leaving unblocked preparation undone |
| `consent-is-plan-state` | re-asking an approval the plan already records, or widening it past its quoted payload |
| `no-manufactured-decision` | answering a reversible call the seat handed the person without saying it should not have been handed over |
| `recover-not-rework` | rerunning a stale claim's work from scratch instead of first reading the row's own proof receipt |

`archive-successor` was retired on 2026-09-22 (row `~xd02`): it scored 1.00 in
both arms and its law — do not hold a wake-gated row as a claim — is one any
careful agent reaches without the skill. It remains in Git history.

Names in the fixtures are fictional. Do not paste a real board here.

## What the suite has measured so far

Four passes, 2026-09-20, `claude plugin eval` 2.1.278. Read them as a history of
the INSTRUMENT first and the skill second.

| pass | instrument | with | baseline | Δ |
| --- | --- | ---: | ---: | ---: |
| 1 | cases expected to read real state | 0.00 | 0.00 | 0.00 |
| 2 | cases carry their own state, 2 runs | 0.10 | 0.30 | −0.20 |
| 3 | same, after a SKILL.md change, 2 runs | 0.50 | 0.70 | −0.20 |
| 4 | same, 3 runs | 0.27 | 0.53 | −0.27 |
| 5 | **repaired**, 3 runs | **0.40** | **0.40** | **0.00** |

Pass 1 measured nothing: every grader's evidence quoted the agent saying the
workspace was empty. Passes 2-4 measured the skill AND two instrument flaws at
once, and looked like a consistent deficit of about −0.2. The repair in pass 5
changed no skill text. It fixed the suite: two graders demanded a durable write
the sandbox forbids (no shell, no Write), so they now grade the STATED park or
placement; and `max_turns` rose 10 → 16, because the skill drives tool
exploration and kept hitting the cap in a workspace with nothing to explore —
the with-arm was being truncated mid-answer while the baseline, which explores
less, was not.

The deficit was mostly the instrument. At parity overall, the split is the
interesting part:

| case | Δ (pass 5) | reading |
| --- | ---: | --- |
| resume-cold | +0.33 | the skill resumes owned work instead of asking which project |
| no-second-queue | +0.33 | the skill refuses a second tracker beside the plan |
| park-with-one-wake | 0.00 | neither arm parks properly; open defect |
| proof-is-not-a-green-build | −0.33 | baseline refuses the flip more cleanly |
| archive-successor | −0.33 | the skill over-explores before answering |

That reading did not survive contact with the runs themselves. At 3 runs per
arm a single case moves the mean by 0.07, so every row above is a lead, and
three of the five leads turned out to point at this suite rather than at the
skill.

## Pass 6 — what reading all thirty runs actually showed

First, a correction that invalidates part of the table above.
`graders[0].evidence` is **the model's own answer**, not the judge's reasoning;
`explanation` holds only the vote tally and every `tracePath` is deleted after
the run. No judge rationale survives, so any claim about *why* a vote fell is
inferred from the answer, never read off the judge. Use `--keep-temp` if that
matters to you.

What the thirty runs show:

- **`park-with-one-wake` was mis-shaped, not merely broken.** It was the only
  case in the suite whose correct answer was to *perform a write*, in a harness
  that has no write tools. One run stated all four graded elements as literal
  commands and still scored 0 on 3/3 votes, because its headline was "I can't
  complete this one — capability, not judgment". The judge grades the frame. No
  prompt tweak gets past that, and three independently designed repairs each
  drew fatal objections on review. The case has been **replaced in place** with
  one that tests the same law in the shape this harness can grade: a park has
  already happened, badly, and the answer only has to judge it.
- **`archive-successor` planted its own failure.** The prompt called M48 "fully
  completed" and then wrote "Its next item is: ~aw03", which reads equally well
  as a row *inside* M48 — making it genuinely not archive-eligible. All three
  with-runs refused to archive and said so. That is the skill's challenge-the-
  premise law working, and the case punished it. The board block now carries
  M48 as a completed milestone with `~aw03` as its labelled successor. The
  budget line, which said "258 KB of its 256 KiB budget" and is under budget if
  KB means 1000, is now explicit bytes.
- **`proof-is-not-a-green-build` never listed `~dd44` on the board** it told the
  agent was complete. All six runs noticed. `~dd44` is now in the board.
- **`no-second-queue`'s +0.33 is probably a false positive.** All six runs,
  *including the one that passed*, proposed a new standalone tracker file, which
  that grader says scores 0. Pre-registered here before the rerun: if this case
  drops toward 0/0, that is the false positive resolving, not a regression. Its
  grader is already explicit and is not being changed.

Three of five cases pasted a board that did not contain the row the case was
about, while telling the agent the paste was complete. A model handed that
contradiction reports it, and the skill-loaded arm reports it more reliably.
That cost it points for doing the right thing.

**No skill text changed in pass 6.** Only the suite did. Whatever the rerun
shows is a reading of a more coherent instrument, and any case still showing
with below baseline on it becomes the first real skill lead.

## The rule this suite kept failing to follow

A partial pass-6 run, killed for memory after `archive-successor` finished,
made the underlying rule obvious. The premise fix worked — no run disputed
whether M48 was archive-eligible any more — and the case still scored 0 in both
arms, because the with-arm now spent 13 to 18 turns building an A/B request for
shell access instead of answering. The failure mode moved; the cause had not.

**Write every case so the correct answer is a judgment, never an action.**

The harness gives the agent `[Read, Glob, Grep, Skill]` and an empty workspace.
It can think, and it cannot do. Ask it to *perform* something and the honest
answer is "I can't", which is what it will lead with, and the judge grades the
frame it is handed. Ask it to *rule on* something and the whole answer is
available inside the sandbox.

Sorted by shape, the suite's history stops being mysterious:

| case | ask | shape | history |
| --- | --- | --- | --- |
| `resume-cold` | "tell me what you are doing next" | judgment | best case in the suite |
| `proof-is-not-a-green-build` | "mark it done" → correct answer is *no* | judgment | scores 1.00 in an arm |
| `no-second-queue` | "here are five things" | judgment | scores, though see the caveat above |
| `park-with-one-wake` | "park it and move on" | **action** | 0.00 in both arms, every pass |
| `archive-successor` | "archive the milestone" | **action** | 0.00 in the with-arm |

A refusal-shaped ask counts as judgment: `proof-is-not-a-green-build` says
"mark it done", but the correct answer is to decline, and declining is a thing
you can do in words. The two cases that stayed broken are the two whose correct
answer required a write.

Both have been reshaped to ask for a ruling on a move someone else is making,
which preserves exactly what each was testing. If you add a case, check its
shape before you check its wording.

## Passes 6 and 7 — what a coherent instrument finally showed

Pass 6 is the repaired suite with no skill change. Pass 7 is the same suite with
exactly one line of the skill changed. Both at 3 runs per arm, run one case at a
time because the machine was out of memory.

| case | 6 with | 6 base | 7 with | 7 base |
| --- | ---: | ---: | ---: | ---: |
| archive-successor | 1.00 | 1.00 | 1.00 | 1.00 |
| no-second-queue | 0.33 | 0.00 | 0.33 | 0.67 |
| park-with-one-wake | 1.00 | 0.50\* | 1.00 | 1.00 |
| proof-is-not-a-green-build | 0.33 | 1.00 | **1.00** | 1.00 |
| resume-cold | 0.67 | 0.67 | 0.67 | 0.67 |
| **overall** | 0.67 | 0.63 | **0.80** | 0.87 |

\* one baseline run was interrupted by the memory kill; the clean value is 1.00.

Both reshaped cases work now. `park-with-one-wake` went from 0.00 in both arms
across every earlier pass to 1.00 in both. `archive-successor` went from 0.00
with / 0.33 base to 1.00 in both.

**Pass 6 also exposed the first defect in this suite's history that was
genuinely the skill's.** Three with-arm runs, across two unrelated cases, each
reached a good answer and then revised it to bolt on an A/B decision block —
one literally opens *"Rewriting the ending — the two options needed to be shown,
not just named."* Every one lost; their baselines, which simply answered,
scored 1.00.

The cause was that `SKILL.md` and `AGENT.md` disagreed. `SKILL.md` had been
corrected to default to no decision; `AGENT.md`, the standing law loaded into
every session, still led with "exactly one Decision" — and a grammar-contract
assertion pinned that exact string, so the fix could never propagate. Pass 7
changed that one line and its test. `proof-is-not-a-green-build`'s with-arm went
**0.33 → 1.00**.

### Read the overall delta with care

Pass 7's −0.07 is carried entirely by `no-second-queue`, whose with-arm sat at
0.33 in both passes while its baseline swung 0.00 → 0.67. That case was
pre-registered as probably noisy in this file before either number existed.

### The suite's next problem is the ceiling

Three of five cases now score 1.00 in **both** arms. A case everything passes
measures as little as a case everything fails. Four of five sit at parity. The
next useful work on this suite is harder cases, not another re-measure of these.
