# Reference Overview

This section groups the repo's durable reference material: prompt structure, plan structure, commands, scripts, the local browser UI, hooks, and configuration.

## Plan and prompt references

- [PLAN.md Field Reference](/reference/plan-fields) explains the task states, annotations, decision log tags, and progress entries used by vidux plans.
- [Prompt Template](/reference/prompt-template) documents the lane prompt structure used throughout the docs site.

## Operational references

- [Commands](/reference/commands) summarizes the `/vidux` and `/vidux-status` command specs stored in `commands/`.
- [Scripts](/reference/scripts) lists the shipped scripts and support libraries in `scripts/`.
- [Browser UI](/reference/browser) documents the local `vidux-browse` launcher plus the read-mostly browser server, artifact shelf, and anchored comment surface in `browser/`.
- [Hooks](/reference/hooks) explains the optional git hooks in `hooks/`.
- [Configuration](/reference/config) summarizes `vidux.config.json` and `vidux.config.example.json`.

## Suggested use

- Start with [PLAN.md Field Reference](/reference/plan-fields) when you need to read or repair a plan.
- Use [Commands](/reference/commands) when you are checking how the prompt-layer commands are supposed to behave.
- Use [Browser UI](/reference/browser) when you need the repo's local plan viewer, artifact shelf, anchored comments, or loopback-only note drop.
- Use [Scripts](/reference/scripts) or [Hooks](/reference/hooks) when you are wiring the repo into a local automation workflow.
