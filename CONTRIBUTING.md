# Contributing

Shadow is MIT-licensed and prepared for public reuse, critique, and feedback.

Current policy:

- Please open Issues for bugs, gaps, critiques, and adoption feedback.
- External pull requests are not being accepted right now. `.github/PULL_REQUEST_TEMPLATE.md`
  exists for PRs the maintainer or their agents open against this repo — its
  presence isn't an invitation for unsolicited external PRs; the policy above
  still applies.
- If you build on Shadow, examples and field reports are especially useful.
- Please do not propose integrations that sync Shadow state into an external
  project-management board. Shadow's queue authority is `PLAN.md` in git; teams
  can mirror that state by hand, but Shadow will not round-trip it.

Why:

- The doctrine is still being tightened.
- The portable core is intentionally small and opinionated.
- Feedback is high-signal right now; code intake is not.
- Board sync creates a second queue authority, which is the failure mode Shadow
  is designed to avoid.

If that policy changes, this file will change first.

## Running the tests locally

Useful for verifying a bug report or exploring the codebase even though PRs
aren't merged right now:

```bash
scripts/shadow-python.sh -m unittest discover -s tests -p 'test_*.py'
bin/shadow init --here && bin/shadow lint   # init makes the plan the grammar check lints
scripts/shadow-python.sh scripts/shadow-release-package.py --allow-dirty
```

Those are the three commands CI runs. There is nothing to install first: Git,
Bash, and Python 3.10+ are the whole toolchain. npm was removed on 2026-08-09,
so any `npm run ...` you find in an older document is stale.

## Code style

There's no linter/formatter config in this repo (no ESLint/Ruff/Prettier) —
match the surrounding file's formatting. Prose in the agent-facing files
(`AGENT.md`, `SKILL.md`, `docs/reference/`) follows the house style: say the
mechanism, name the file, and drop anything that does not change a decision.
