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
| Durable memory of what work is trying to achieve | The repo's `PLAN.md` — Brief, Tasks, Progress. Git is the sync layer. |
| "It just knows which tools/flows fit this work" | The milestone's `- tools:` line, written by whoever worked the milestone; `shadow amp` projects it into every goal block. Knowledge rides IN the plan. |
| Continuity across CLIs, providers, machines | The plan pointer (`repo + PLAN.md @ ref + section`) plus the portfolio fallback in `shadow status`. A chat is a projection; the plan is the memory. |
| Learned lessons that persist | The shipping commit's folded LESSON, Progress lines, and skills — never a side database. |

## Why not install a memory service anyway

- A store that answers faster than `PLAN.md` becomes the authority by
  convenience, and the plan rots — the precise failure v4 was built to end.
- Every honcho capability above already has a git-durable home with a
  mechanical enforcer (`shadow lint`, `shadow accept`).
- The observed failure honcho keeps being reached for — "shadow opened
  somewhere new and knew nothing" — was an entry-point bug (empty cwd scan),
  not a memory gap. Fixed by the portfolio fallback, not by a database.

## If the ruling should change

Open a spike in the shadow repo's `PLAN.md` (`SPIKE ~hash ... | ends: <date>`)
naming the concrete capability `PLAN.md` + git cannot carry. It ends in a
written keep/kill/promote decision like any other spike. Until such a spike
promotes, agents do not install, recommend, or scaffold a honcho service, and
they answer this question by linking here.
