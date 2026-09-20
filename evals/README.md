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
| `park-with-one-wake` | parking without a durable record, an exact wake, or releasing the claim |
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

The skill wins the two cases that encode its purpose and loses two where it
talks more than it decides. That is a working measurement, not a verdict: at 3
runs per arm a single case moves the mean by 0.07, so treat any one row as a
lead to chase, never a score to quote.
