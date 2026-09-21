# Eval suite — does this skill change what the agent does?

Five cases, run by `claude plugin eval` with its no-plugin baseline arm:

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
| `park-with-one-wake` | calling a park done when its wake is not checkable, its claim is still held, and its seat then stopped |
| `archive-successor` | archiving a milestone and leaving a calendar-gated successor held |

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
