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

2026-09-20, `claude plugin eval` 2.1.278, 2 runs per arm, 3 judge votes per run:

| case | with (before) | with (after) | baseline (before) | baseline (after) |
| --- | --- | --- | --- | --- |
| archive-successor | 0.00 | 0.50 | 0.00 | 1.00 |
| no-second-queue | 0.00 | 0.50 | 0.00 | 1.00 |
| park-with-one-wake | 0.00 | 0.00 | 0.00 | 0.00 |
| proof-is-not-a-green-build | 0.00 | 0.50 | 1.00 | 1.00 |
| resume-cold | 0.50 | 1.00 | 0.50 | 0.50 |
| **mean** | **0.10** | **0.50** | **0.30** | **0.70** |

"Before" and "after" differ by one change to `SKILL.md`: the Brief's decision
element became conditional. In the before run, EVERY with-arm response ended in
a manufactured A/B/C menu for work the seat could have finished itself; the
graders failed them for handing the decision back.

Read the numbers honestly: the with-arm mean rose 0.10 → 0.50, but the baseline
mean rose 0.30 → 0.70 in the same re-run, so run-to-run variance is not excluded
and the change is NOT established as the cause. The gap to baseline is unchanged
at -0.20 in both runs. The skill does not yet beat no-skill on these five cases.
That is the finding, and it is why the suite exists.
