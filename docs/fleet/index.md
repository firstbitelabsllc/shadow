# Fleet Overview

Vidux automation is opt-in. The core discipline works without long-running lanes, but this repo also ships guidance for scheduled runs, fleet coordination, and platform-specific lifecycle details for Claude Code and Codex.

For Codex, the docs in this section cover the native automation path on macOS. The automation guide treats `Chat` as the default for Codex-created automations; use the TOML + DB flow only when you explicitly want a repo-bound `Local` or `Worktree` lane.

## What lives in this section

- [Claude Code Lifecycle](/fleet/claude-lifecycle) documents how a Claude lane fires, reads authority files, and checkpoints.
- [Codex Automation Lifecycle](/fleet/codex-lifecycle) documents the native Codex Mac app automation model and its persistence rules for repo-bound lanes.
- [Codex Setup Guide](/fleet/codex-setup) walks through the TOML + database + app-restart sequence used for native `Local` or `Worktree` Codex lanes on macOS.
- [Platform Comparison](/fleet/platforms) explains when the repo prefers Claude Code versus Codex.
- [Harness Authoring](/fleet/harness) summarizes the prompt authoring rules from `guides/harness.md`.
- [Fleet Operations](/fleet/operations) summarizes the coordination rules from `guides/automation.md` and `guides/fleet-ops.md`.
- [Recipe Catalog](/fleet/recipes) maps the reusable patterns shipped in `guides/recipes.md` and `guides/recipes/`.

## When to automate

The automation guide says to automate only when all of these are true:

- Work spans multiple sessions and would lose context across handoff.
- The cycle is repeatable across fires.
- State orientation can live on disk: owning `PLAN.md`, publish ledger rows, evidence, and lane-local `memory.md` notes.
- You accept disposable sessions in exchange for steady progress.

## When not to automate

The same guide says to stay manual when any of these are true:

- The work needs live human judgment every step.
- The cycle cannot be described in a self-contained prompt.
- The state would have to live in session memory.
- The task is a one-off fix that can be done directly.

## Shared lifecycle spine

Every runtime follows the same Vidux proof spine, even though scheduling differs:

1. Resolve local config with `vidux config check --json`.
2. Run pre-task runtime health with `scripts/vidux-doctor.sh --json`, not the slower terminal `vidux doctor`.
3. Keep one `VIDUX_SIGNPOST_RUN_ID` across the cycle and emit signposts for `hook.beforeTask`, `subagent.spawn`, `task.verify`, and `hook.afterTask`.
4. Attribute spawned workers with `VIDUX_RUNTIME=claude`, `VIDUX_RUNTIME=codex`, or `VIDUX_RUNTIME=cursor` when the ambient session environment would otherwise mislabel the event.
5. Finish by updating the owning `PLAN.md` plus the matching publish ledger row with proof, handoff status, files claimed, and next-agent resume.

Use `vidux signpost lifecycle-smoke --json` as a local trace-shape smoke before relying on a new lane prompt. Use `vidux signpost spawned-subagent-smoke --json` when the question is inherited Codex parent env plus Claude/Cursor worker attribution. Both are local smokes, not proof that the external runtimes actually launched.

## Suggested reading order

1. Start with [Platform Comparison](/fleet/platforms) if you are deciding between Claude Code and Codex.
2. Read [Harness Authoring](/fleet/harness) before writing or updating prompt files.
3. Use [Fleet Operations](/fleet/operations) for cross-lane rules, worktree handoff, and trunk-health checks.
4. Use [Recipe Catalog](/fleet/recipes) when you need a reusable pattern instead of inventing one from scratch.
