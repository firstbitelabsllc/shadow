# Recipe Catalog

Vidux ships two recipe surfaces:

- `guides/recipes.md` contains the main automation recipe catalog.
- `guides/recipes/` contains smaller focused guides that support recurring patterns.

This page maps that material into the docs site so the VitePress navigation matches the repo.

## Core automation recipes

`guides/recipes.md` currently ships these named recipes:

- `Recipe 1: Fleet Watcher` - deprecated on 2026-04-17.
- `Recipe 2: PR Reviewer` - review automation for pull requests.
- `Recipe 3: PR Lifecycle Manager` - triage, promote, and clean up PRs.
- `Recipe 4: Observer Pair` - deprecated on 2026-04-17.
- `Recipe 5: Deploy Watcher` - verify deploys and stop after a bounded number of checks.
- `Recipe 6: Trunk Health` - detect dirty or diverged main branches early.
- `Recipe 7: Skill Refiner` - audit skill descriptions, stale references, and overlap.
- `Recipe 8: Self-Improvement Loop` - let the repo improve itself from the current plan and docs.
- `Recipe 9: Edit-Then-Verify` - pair changes with a verification pass.
- `Recipe 10: Cron Retry with Backoff` - bound repeated retries.
- `Recipe 11: Multi-PR Dependency Shipping` - handle ordered PR stacks.

## Supplemental guides in `guides/recipes/`

The repo also ships focused recipe documents for recurring surfaces:

- `claude-md-rules.md`
- `codex-runtime.md`
- `env-var-forensics.md`
- `evidence-discipline.md`
- `lane-prompt-patterns.md`
- `lightweight-first.md`
- `proactive-surfacing.md`
- `subagent-delegation.md`
- `user-value-triage.md`
- `visual-proof-required.md`
- `webfetch-fallback.md`

## How to choose

- Use the main recipe catalog when you need a lane shape or operating pattern.
- Use the focused recipe documents when the problem is narrow, such as Codex runtime setup or evidence discipline.
- Use [Fleet Operations](/fleet/operations) for the always-on rules that apply even when no specific recipe is active.

## Practical reading order

1. Start with the recipe in `guides/recipes.md` that matches the automation you want to run.
2. Pull in a focused guide from `guides/recipes/` only if the task actually needs it.
3. Return to [Harness Authoring](/fleet/harness) to keep the prompt itself short and stable.
