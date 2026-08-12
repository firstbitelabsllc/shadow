# Honcho — the ruling, once

Honcho comes up whenever Shadow's memory feels thin: *"isn't the durable
architecture based on honcho? why haven't we installed it?"* This page is the
standing answer, so the question stops costing a re-derivation.

## The ruling

**Honcho is a pattern Shadow implements, not a service Shadow installs.**
Ruled with v4 (2026-08-07), the same release that deleted the roster, route,
seat, and YAML config layers. Nothing named honcho is, was, or should be
running on the machine — an installed memory store would be exactly the
"second store" the platform boundary bans: one more place plan truth could
drift from `PLAN.md`, one more daemon to keep honest.

## What each honcho function maps to

| The honcho idea | Where it actually lives |
|---|---|
| Durable global coordination | This computer's private local root board — project priority, entity pointers, claims, owners, leases, and entity resume checkpoints. Its recovery journal tracks `board.json` only. |
| Durable detail about what work is trying to achieve | Each infrastructure entity's local `PLAN.md` — milestones, checkpoints, decisions, proof, and Progress. Product source is kept separately. |
| "It just knows which tools/flows fit this work" | The milestone's `- tools:` line, written by whoever worked the milestone; `shadow amp` projects it into every goal block. Knowledge rides IN the plan. |
| Continuity across CLIs and providers on one computer | `shadow status --by <seat>` reads the root board and dereferences its entity plan pointers. A chat is only a projection. |
| Continuity across computers | Project Git remotes carry committed entity plans and proof; each computer reconstructs its own root board. One computer never impersonates another's live coordination state. |
| Learned lessons that persist | The shipping commit's folded LESSON, Progress lines, and skills — never a side database. |

## Why not install a memory service anyway

- A second store that answers faster than the root board plus entity plans
  becomes authority by convenience, and the real hierarchy rots.
- Every honcho capability above already has a git-durable home with a
  mechanical enforcer (`shadow lint`, `shadow accept`).
- The observed failure honcho keeps being reached for — "shadow opened
  somewhere new and knew nothing" — was an entry-point bug, not a memory gap.
  It is fixed by the per-computer board and bounded import, not another database.

## If the ruling should change

Open a spike in the shadow repo's `PLAN.md` (`SPIKE ~hash ... | ends: <date>`)
naming the concrete capability `PLAN.md` + git cannot carry. It ends in a
written keep/kill/promote decision like any other spike. Until such a spike
promotes, agents do not install, recommend, or scaffold a honcho service, and
they answer this question by linking here.
