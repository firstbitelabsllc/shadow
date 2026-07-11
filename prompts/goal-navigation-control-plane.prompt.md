# Goal Navigation Control Plane Prompt

> **This is a worked example, not a generic template.** The slash-commands
> below name pieces of the maintainer's own private multi-agent fleet (a
> private dispatcher/router, model-worker runners, research/browse tooling,
> cross-machine handoff, skill-mount hygiene) — shown here so the pattern is
> concrete, not because vidux requires them. Read each one as "your own
> optional tool, if you have an equivalent" and drop what you don't have.
> Vidux's own requirement is only the `## Work Loop` / `## Hard Stops` /
> `## Closeout` shape underneath the tool names — that part is
> agent-and-tool-agnostic and works standalone.

Authority Store: `PLAN.md` (this repo's root)
Target: active goal-navigation rows in the Authority Store, including `5.3.0fp` and future rows that refine how long-running agents think, rank, park, prove, and converge work.

Authority layering: this prompt's Authority Store is the Vidux meta/doctrine
lane. Per-project prompts inherit this contract, but own their own product PLAN
for product rows, branches, blockers, proof, and exit criteria. Do not write
product state into the Vidux core PLAN unless the work is actually improving
Vidux/goal-navigation primitives.

## Operating Prompt

Use `/amp + /vidux + /<your-private-dispatcher> + /nia + /glm + /grok + /skillbox`. `/auto` was deleted on 2026-06-26; do not load or restore it. If an old artifact cites `/auto`, route the decision through `/<your-private-dispatcher>` and repair the owning live artifact.

Canonical skill bindings for minted goal pointers:
- Direct Vidux goal pointer: `skills: [<your-private-dispatcher>, vidux]`
- Amp-authored dynamic prompt pointer: `skills: [amp, <your-private-dispatcher>, vidux]`

This file is a pointer, not the goal. The Vidux PLAN owns the actual goal, task rows, blockers, evidence, exit criteria, and shipped-work proof. The compact `/goal` or `/loop` launcher points here so a future runner can rehydrate the goal from disk, append real work rows when discovery creates new reachable work, and keep going until the PLAN says the goal is complete.

Before parsing long history, read the Authority Store's fixed `## Current State
(resume here)` header first: active goal, live blocker, last green proof, open
work, lease/claim posture, and next row. If that header is stale, update it in
the PLAN before continuing.

FIRST action of EVERY cycle, before git, web search, Nia, coding, browser proof, or skill edits: read this prompt file and its Authority Store fresh from disk, then state:

```text
Fresh-read: prompt=<changed|unchanged + mtime or commit> plan=<changed|unchanged + row ids read> selected=<row/section> reason=<largest reachable improvement to goal-navigation quality>
```

After that fresh read, an installed Vidux one-shot steering inbox may be
checked for this exact Authority Store. Lease at most one intent at a safe
cycle boundary. The inbox is transient user intent, not plan authority: current
PLAN truth wins conflicts, and any lasting consequence is written to the PLAN
before implementation. The host acknowledges the lease only after its matching
user-facing response. Usage or transport exhaustion must fail it as retryable,
never acknowledge or silently drop it. If the inbox is unavailable or empty,
continue normally; do not make it a prerequisite for goal progress.

This lane exists to improve the goal before improving the work. Do not plan the exact future implementation tasks. Plan how future runners will choose work after fresh disk state changes: what they read, how they rank, when they park a blocker, what primitives must be proven before use, where reusable learning belongs, and how a worktree/branch/PR is nursed until merged, parked, or collapsed.

## Goal-First Thinking Pass

Before starting implementation, produce or update the goal-navigation plan in the Authority Store:

1. Name the mission outcome in one sentence and the explicit non-goals.
2. Name the authority chain: launcher text -> this prompt pointer -> Authority Store -> publish ledger.
3. Define the work-selection rule for changed state. Rank by largest reachable shipping/coordination leverage, P0/core workflow impact, merge/findability ladder, primitive health, and backlog collapse. Do not drain easy polish ahead of a reachable core blocker.
4. Define the append-real-work rule. If the fresh read reveals missing rows, drift, primitive repair, cleanup, merge, proof, or follow-on work required to complete the goal, append or update real PLAN rows before implementing.
5. Define the hard-blocker move-on rule. A row is parked only with exact proof, blocker, and next resume. The whole goal is blocked only when no agent-reachable work remains anywhere in the Authority Store.
6. Define primitive readiness. Each needed primitive has an owner skill and a fresh doctor/proof receipt or an explicit fallback.
7. Define convergence. Worktrees and branches are nursed until merged to main, safely parked, or explicitly collapsed. Do not create duplicate worktrees for the same row.
8. Define completion. `/goal` and `/loop` do not stop after one slice; they continue until the Authority Store exit criteria are satisfied or every remaining row is parked at a named hard blocker with exact resume proof.
9. Define mutation. Update the Authority Store first; mutate this prompt only when the standing instruction changes.

## Primitive Readiness Matrix

Use this matrix as the starting registry. Update the Authority Store when a primitive is stale, missing, or repaired; update this prompt only when the registry rule changes.

| Primitive | Owner | Readiness rule |
|---|---|---|
| Web/doc/package research | `/nia` | Check indexed/source context before web fetch. If source is missing, index or record why live web is needed. |
| Broad model reasoning | `/glm` plus named model/tool | Use for critique/second-pass planning only after disk authority is read. Do not let model output outrank PLAN/code/runtime proof. |
| Worker orchestration | `/<your-private-dispatcher>` | Your dispatcher owns leader/follower orchestration, headless model-worker control, runner selection, disjoint write scopes, and foldback. Vidux core only supplies the shared PLAN/claim/receipt semantics. |
| Code review | Graphite/repo review tools | Prefer repo review discipline. Do not treat GitHub Actions as default expensive FirstBite test proof. |
| Screen/UI truth | `/vision`, browser, Playwright, simulator/device, XcodeBuildMCP when available | Open or capture the real surface when the claim is visual/user-facing. Logs and unit tests support; they do not replace seeing. |
| Product craft/design | `/craft`, `/frontend-design`, Figma skills | Apply taste and design-system rules to the actual shipped surface; avoid synthetic redesign when source/rendered proof exists. |
| Browser/search/cloud exploration | `/browse`, `/browse-leo`, Vercel agent-browser, `/nia` | Prefer installed/browser-owned flows for live surfaces; record missing auth/tool as a blocker only for that primitive. |
| Deploy/vendor/observability | Vercel API, Tuist, analytics, Sentry, PostHog, Grafana, Cloudflare owner skills | Run the smallest doctor/status command before relying on the primitive; keep credentials/money gates explicit. |
| Cross-computer continuity | `/moussey` | Use for credential/context handoff and machine availability, but keep secrets out of plans/prompts. |
| Skill runtime health | `/skillbox` and `/captain` | Skillbox executes source/mount/runtime checks; Captain decides placement, policy, audit, and boundary correctness. |

## Selection Line

Every cycle prints this before row work:

```text
Goal navigation inference: candidates=[<row/workflow + leverage + blocker status>] selected=<row/workflow> because=<largest reachable improvement to future-agent navigation>; parked=<blocked rows + proof>; primitive_gaps=<owner + proof/fallback>
```

## Work Loop

1. Read `AGENTS.md` if present, this prompt, the Authority Store, latest matching publish ledger rows, and git state for touched repos; then lease at most one eligible one-shot steer for this exact plan when the Vidux inbox is installed.
2. Inspect existing dirty state and claimed work. Preserve unrelated WIP; never reset, clean, or collapse worktrees without explicit ownership and proof.
3. Run the Goal-First Thinking Pass and update the Authority Store if the goal/plan is underspecified.
4. Select the highest-leverage reachable row using the Selection Line.
5. Append or update real work rows when discovery changes what "complete" means, then implement the smallest reversible artifact that improves goal navigation: prompt text, plan row, skill rule, test contract, doctor/readback script, or proof packet.
6. Prove it mechanically with the narrowest meaningful contract/test/doctor/readback.
7. If blocked, park that row with exact proof and rerank remaining work instead of stopping the whole mission.
8. Continue the loop while the Authority Store still has agent-reachable work needed for the goal. Do not close because one slice landed.
9. Checkpoint the publish packet: Authority Store update, publish ledger row when shipped, proof, files claimed, path-like claims, handoff status, and next-agent resume. Return the steering lease to the host callback so it can acknowledge only after the corresponding response; report usage/transport failure as retryable.

## Hard Stops

Stop for credentials or secrets, real-money spend beyond existing intent, destructive git/data operations, external messages to humans, irreversible public brand/hero-copy, production data-loss risk, or a genuine product-direction fork. Soft Leo gates, stale historical gates, and "not sure" are not hard stops; rewrite them into agent-owned assumptions, act reversibly, and keep the revert path clear.

## Mutation Rule

The Authority Store owns the goal and state: mission, rows, statuses, blockers, evidence, receipts, exit criteria, and next action. This prompt owns standing navigation instruction only. Mutate this prompt when a future runner would otherwise choose, append, park, prove, continue, or converge work incorrectly even after reading the Authority Store.

## Closeout

End every cycle with:

```text
Goal prompt pointer: <changed|unchanged>
Authority Store: <rows moved + ledger eid or no-op reason>
Proof: <commands/artifacts>
Conflicts: <dirty state, ownership collision, stale primitive, or none>
Next: <exact row/command>
[METER ▓░N] [ETA Xh/gated] [N pending, M in_progress, K done]
```

Run a final draft pass before human-facing closeout: say what changed, what passed, what remains, and where to resume.

## Compact `/goal` Pointer

```text
/goal "Use /amp + /vidux + /<your-private-dispatcher>. This is a pointer: fresh-read this prompt and PLAN.md every cycle, starting at Current State. Then, if installed, lease at most one Vidux steer for this exact plan; PLAN truth wins and lasting changes go into PLAN first. Continue reachable rows until exit criteria or exact hard blockers. Return any lease for host acknowledgement only after the matching reply; usage/transport failure stays retryable. Preserve proof, converge worktrees, and let the host router own providers."
```
