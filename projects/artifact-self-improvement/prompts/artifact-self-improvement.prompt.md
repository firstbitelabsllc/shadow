# Artifact Self-Improvement Prompt

Authority Store: ~/Development/vidux/projects/artifact-self-improvement/PLAN.md
Target: ASI tasks in `## Tasks`

## Operating Prompt

FIRST action of EVERY cycle: read this prompt file and the Authority Store
fresh from disk before git, web, Sentry, or worktrees. State what changed or
unchanged and which ASI rows you selected.

Drive artifact-producing skill improvement across `~/Development/ai`,
`~/Development/ai-leo`, and `~/Development/vidux`.
"Artifact" means code, tests, docs, reports, prompt files, plans, PR bodies,
screenshots, browser HTML, dashboards, design specs, runbooks, or any durable
output someone can open later.

When the mission is launch, 2.0, readiness, or product quality, choose the true
P0 UX/core workflow row first across every target platform. Infer P0 by
user-visible workflow correctness, launch-blocking impact, findability, and
proof value, not by how tidy or quick the task looks. P2/P3 work is valid only
when it directly unblocks or proves that P0, no unblocked P0 exists, or the
Authority Store explicitly promotes it.

For each cycle, produce exactly one bounded improvement outcome:

- improve the artifact itself,
- add one reusable rule to the owning skill or prompt,
- bookmark a stable fact through `/local`,
- publish a ledger/plan receipt that makes the artifact findable, or
- record why no reusable lesson exists.

Do not widen into endless skill prose. Shared/core skill changes must pass the
stranger-repo test; Leo-private defaults belong in `/ai-leo`; project facts stay
in repo plans, prompt files, brand skills, or local memory.

## Skill Bindings

- `/vidux` owns PLAN discipline, prompt-file mutation rules, and bounded
  self-improvement rows.
- `/amp` owns compact dynamic prompt launchers and rejects unbounded
  "keep improving skills" prompts.
- `/auto` owns Leo-private no-wait defaults and the drive-by artifact
  self-improvement decision.
- `/slop` owns the truth/taste gate for artifact claims and proof theater.
- `/local` owns stable reusable facts; never cache transient status or secrets.
- `/ledger` owns publish/handoff receipts that make artifacts findable.

## Mutation Rule

Update this file only when the standing instruction changes. Append task,
status, proof, blocker, and progress changes to the Authority Store first.

## Closeout

Run a final `/slop` pass over any human-facing artifact or status. End every
cycle with `[METER ▓░N] [ETA Xh] [N pending, M in_progress, K done]`.
