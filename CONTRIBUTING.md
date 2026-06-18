# Contributing

This repo is public for reuse, critique, and feedback.

Current policy:

- Please open Issues for bugs, gaps, critiques, and adoption feedback.
- External pull requests are not being accepted right now.
- If you build on Vidux, examples and field reports are especially useful.
- Please do not propose integrations that sync Vidux state into an external
  project-management board. Vidux's queue authority is `PLAN.md` in git; teams
  can mirror that state by hand, but Vidux will not round-trip it.

Why:

- The doctrine is still being tightened.
- The portable core is intentionally small and opinionated.
- Feedback is high-signal right now; code intake is not.
- Board sync creates a second queue authority, which is the failure mode Vidux
  is designed to avoid.

If that policy changes, this file will change first.
