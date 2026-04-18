# ASK-LEO — vidux

Durable queue of questions the fleet has for Leo. Lanes write `[ASK-LEO Q<N>]` entries in their memory.md pointing at a row here. Leo answers inline (fill the `Answer:` line). On the next cycle, the lane reads the answer, acts, and logs `[ACTED Q<N>]`.

Why this exists: memory.md cycles are ephemeral. Durable questions live here so they accumulate state, not re-summaries.

---

## Q1 — Bypass Greptile-wait on vidux repo?
Opened: 2026-04-18T02:16Z | Status: pending | Lane: vidux-ship-coordinator
PR #25 precedent is OWNER-merge (merged 2026-04-13 without Greptile review row). Greptile is not configured on `leojkwan/vidux`. Vidux-ship prompt §5 Phase A requires Greptile, which will never fire here.
Options:
  a) Authorize OWNER-merge on #26 (matches PR #25 precedent)
  b) Require explicit "ship it" comment from you on each PR
  c) Gate on a different reviewer (Sentry / Claude-code-review / none)
Answer:

## Q2 — PR #27 scope-split: accept bundle or split?
Opened: 2026-04-18T09:45Z | Updated: 2026-04-18T19:15Z | Status: pending | Lane: vidux-ship-coordinator
PR #27 branch `claude/vidux-recipes-split` now carries **7 releases stacked**: 2.10.0 (refactor) + 2.11.0 (/vidux-status + [ETA: Xh]) + 2.12.0 (mandatory ETA + [FREEFORM]/[METER]) + 2.13.0 (ASK-LEO queue + tightened marker doctrine) + 2.14.0 (scripts/vidux-status.py) + 2.15.0 (L1/L2 retired + cross-tool removed + config surfaced) + 2.16.0 (audit cleanup — Mode A/B rename + breadcrumb fix + archive). PR title still reads "refactor(2.10.0)" which has not been accurate since 2026-04-18T05:00Z.
Options:
  a) Accept combined — retitle #27 to cover all 7 releases, ship together after Q1 resolves
  b) Force-push revert on `claude/vidux-recipes-split` down to 2.10.0, cherry-pick 2.11→2.16 onto fresh branches, open 6 separate PRs
  c) Leave as-is, ship as-is with unfortunate title
Answer:
