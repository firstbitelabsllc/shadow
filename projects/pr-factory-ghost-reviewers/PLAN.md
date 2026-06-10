# PR Factory Ghost Reviewers

## Status

Active as of 2026-06-09.

## Goal

Make PR Factory own durable ghost-review orchestration instead of spawning
one-off reviewer prompts from chat.

## Boundary

- Sloth stays the live team/PR/Jira/Slack metadata scout.
- PR Factory owns ghost-review workflow and config.
- Leo Flow routes review/slop requests to PR Factory.
- Vidux owns this project plan and progress receipts.

## M1

1. Add `skills/pr-factory/config/ghost_reviewers.yaml`.
2. Teach PR Factory the ghost-review contract.
3. Use the 20-reviewer Sloth roster as simulated lenses only.
4. Require `APPROVE <name>` or `BLOCK <name>: <file:line issue>`.
5. Keep max parallel at 4 to match current subagent limits.
6. Do not claim real teammate approval.

## M2

1. Add a tiny PR Factory helper that expands YAML reviewers into prompts.
2. Record run receipts in a PR-local evidence note, not in Sloth config.
3. Let Leo Flow route `ghost reviewers` to PR Factory review mode.
4. Keep Sloth as the live roster source and refresh this YAML deliberately.

## Proof

- Config parses as YAML.
- PR Factory mentions the config and the no-real-approval rule.
- Current AI Slop run reaches 20 ghost approvals before commit.
- Sloth remains mounted and separately routed by Leo Flow.
