# ASK-LEO — vidux

Durable queue of questions the fleet has for the repo owner. Lanes write
`[ASK-LEO Q<N>]` entries in their memory.md pointing at a row here. The
owner answers inline (fill the `Answer:` line). On the next cycle, the lane
reads the answer, acts, and logs `[ACTED Q<N>]`.

Why this exists: memory.md cycles are ephemeral. Durable questions live
here so they accumulate state, not re-summaries.

---

## Q1 — Example: which merge policy applies when no review bot is configured?

Opened: 2026-01-01T00:00Z | Resolved: 2026-01-01T12:00Z | Status: resolved | Lane: example-lane

A PR needs to merge but the repo has no automated review bot configured.
Options:
  a) Owner-merge on documented precedent from a prior PR
  b) Require an explicit "ship it" comment from the owner on each PR
  c) Gate on a different reviewer

Answer: (a) — codified as standing policy once decided; future PRs in the
same situation follow the same precedent without re-asking.

---

This example entry is the only content shipped here — real accumulated
Q&A history is operational and repo-owner-specific, not publishable
documentation. If you fork this repo and start using the fleet doctrine,
this file will fill up with your own real questions; scrub it (or
gitignore it locally) before republishing a fork.
