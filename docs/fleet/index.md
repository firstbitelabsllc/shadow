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
- [Linear Port Audit](/fleet/linear-port-audit) records the latest read-only board-wiring audit across Vidux, StrongYes, and Resplit repos.
- [Recipe Catalog](/fleet/recipes) maps the reusable patterns shipped in `guides/recipes.md` and `guides/recipes/`.

## When to automate

The automation guide says to automate only when all of these are true:

- Work spans multiple sessions and would lose context across handoff.
- The cycle is repeatable across fires.
- State can live on disk in files such as `PLAN.md`, `memory.md`, and ledger data.
- You accept disposable sessions in exchange for steady progress.

## When not to automate

The same guide says to stay manual when any of these are true:

- The work needs live human judgment every step.
- The cycle cannot be described in a self-contained prompt.
- The state would have to live in session memory.
- The task is a one-off fix that can be done directly.

## Suggested reading order

1. Start with [Platform Comparison](/fleet/platforms) if you are deciding between Claude Code and Codex.
2. Read [Harness Authoring](/fleet/harness) before writing or updating prompt files.
3. Use [Fleet Operations](/fleet/operations) for cross-lane rules, worktree handoff, and trunk-health checks.
4. Use [Recipe Catalog](/fleet/recipes) when you need a reusable pattern instead of inventing one from scratch.
