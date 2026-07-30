# Recipe: Evidence Discipline

> Never attribute behavior to a cause without concrete evidence. Never claim "done" without verification.

## When to use

- Explaining why something broke, flaked, or behaves unexpectedly
- About to mark a task `[completed]` in a plan file
- Tempted to write "probably" or "likely" in a root-cause claim
- Debugging a cross-system symptom

## The recipe

**1. No cause without evidence.** Cite logs, commits, diffs, traces, or concrete output. If you don't have evidence, say "I don't know yet" and investigate.

**2. "Probably" is not evidence.** Label a plausible explanation as a
hypothesis and name the observation that would confirm or reject it.

**3. Never mark `[completed]` without running a verification command.** Build, test, curl, screenshot — in the same session — and confirm the output. A plan entry set to `[completed]` without verification evidence is a lie.

**4. State what you ran.** The commit or plan note must name the verification
command, result, and revision. "Tests pass" is weaker than "`pnpm test` passed
at `abc123`."

**5. When uncertain, split the claim.** "The parser receives an empty value
(verified by the failing fixture). I do not yet know which caller removed it."

## Failure modes

Without this recipe:

- A network error is attributed to another process with no supporting log.
- The first fix changes the wrong layer because the cause was never isolated.
- A plan marks work complete before the named acceptance check runs.
- A quiet worker failure is summarized as a clean result.

## Example

**Wrong:**

> The parser probably drops the field.

**Right:**

> The failing fixture reaches `parseRecord` with the field present, while the
> post-normalization assertion sees it missing. The normalizer is the smallest
> currently supported fault boundary; the exact branch remains to be isolated.

**Wrong:**

> [completed] Fixed the font loading issue.

**Right:**

> [completed] Fixed the font loading issue — ran `pnpm build && pnpm e2e` at
> `abc123`; both passed, and the attached screenshot shows the expected font on
> the guest flow.

## See Also

- `guides/recipes/visual-proof-required.md` — the specific verification flavor for UI work
- `guides/recipes/env-var-forensics.md` — concrete evidence checklist for env-var mysteries
