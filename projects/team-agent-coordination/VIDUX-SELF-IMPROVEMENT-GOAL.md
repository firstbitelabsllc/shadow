# Vidux Self-Improvement Overnight Goal Prompt

Generated: 2026-06-01

Owner plan: `projects/team-agent-coordination/PLAN.md`

Use this as a paste-ready `/goal` prompt for an overnight or week-long lane whose job is to make Vidux better at running long-horizon concurrent agent projects.

## Prompt

```text
Load: /vidux, /pilot, /pilot-leo, /ledger, /auto, /amp.

Mission: improve Vidux by dogfooding Vidux on Vidux. Build the durable loop for week-long, multi-agent, concurrent projects where every publish/change immediately updates its owning plan, ledger row, proof trail, and next-agent resume point. Keep working until the queue is drained, a real external blocker appears, or the meter is exhausted.

Authority files:
- /Users/leokwan/Development/vidux/PLAN.md is the Vidux core plan.
- /Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md owns cross-agent coordination, claims, cron registry, Goal Mode, and ledger propagation.
- /Users/leokwan/Development/vidux/projects/agentic-command-center/PLAN.md and projects/agentic-coding-workbench/PLAN.md are proof/cockpit consumers only if UI/API proof is needed.
- /Users/leokwan/Development/vidux/SKILL.md is the shared discipline. /pilot is a redirect. /pilot-leo is Leo's overlay and must not be policy-edited unless Leo explicitly asked. /ledger owns append-only activity truth.

READ first:
1. AGENTS.md or repo instructions, then git status and dirty diffs. Preserve dirty WIP.
2. The authority plans above, plus rg for existing same-surface rows before creating anything.
3. Run ledger current-state checks:
   bash ~/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
   ~/Development/ai/hooks/ledger-fleet-health.sh --repo vidux --archive
   ~/Development/ai/hooks/ledger-brief.sh --repo vidux --entries 20 --hours 24
4. Check real surfaces when relevant: Vidux browser, local docs build, tests, and any cockpit endpoint being changed.

Definition of win:
- A Vidux publish/change cycle can answer: what changed, which plan row moved, which ledger row recorded it, what proof passed, what drift was reconciled, what remains, and who can resume.
- Plan-silent publish is impossible by doctrine, hook, test, or recipe. A commit/PR/push/hook-install/release without plan and ledger propagation is a defect.
- Long projects have clear claims, subplans, stale-proof gates, self-review checkpoints, and handoff_status so a new agent can resume after days without chat memory.

Work queue:
P0. Publish propagation invariant: every publish action must update the owning PLAN.md Progress/Tasks or Drift Log and emit a ledger row:
    ~/Development/ai/hooks/ledger-emit.sh --event publish --repo-path /Users/leokwan/Development/vidux --lane vidux-self-improvement --task-id <task-id> --plan-path <PLAN.md> --proof "<command/artifact>" --handoff-status <done|in_progress|blocked|needs_review> --resume "<next-agent resume point>" --file <changed-file> --claim <claimed-file> --skills vidux,pilot-leo,ledger
P1. Self-scrutiny gate: before publish, run three review passes, as subagents if available or sequentially if not:
    - invariant auditor: plan/ledger/drift/claim propagation is complete
    - regression runner: tests, docs build, lint, browser proof where relevant
    - adversarial reviewer: find overclaims, stale proof, duplicate plan, unsafe publish, or policy drift
   Fix P0/P1 findings before publishing. Record NAY rationale only for lower-risk findings.
P2. Week-long project contract: strengthen Vidux docs/scripts/tests so compound work always has one canonical plan, optional L2 subplans only when needed, claims and files_claimed, stale-proof detection, meter checkpoints, and next-agent resume instructions.
P3. Claims and collision hygiene: continue or implement the existing team-agent-coordination claims bus and automation_name work only when it advances code plus proof, not bookkeeping.
P4. Dogfood proof: run the improved loop on Vidux itself. Use vidux drift/signpost when actual work diverges from planned work. Save proof paths in the plan and ledger.

Operating rules:
- Start with [in_progress] rows before new work. If the same surface already has a plan row, append there. Do not spawn a sibling plan.
- Keep lanes small: coordinator plus at most 2 focused workers unless a plan explicitly authorizes more. No persistent observer lanes; scrutiny must become fixes, tests, hooks, or plan constraints.
- No destructive git. No reset/clean/force-push. No direct main push unless the repo plan and /pilot-leo precedent clearly allow it and the publish gate is green. Prefer feature branch plus ready PR for reviewable changes.
- Progress is code change. If a cycle only discovers facts, update local plan/progress and keep moving; do not open plan-only PRs.
- Every final checkpoint includes: changed files, commands/proof, ledger eid or dry-run payload, plan row moved, non-claims, and next resumable task.
```

## Notes

- `projects/team-agent-coordination/PLAN.md` is the owning lane because it already tracks Goal Mode, automation identity, claims, and fleet coordination.
- The prompt intentionally treats `/pilot` as a redirect through `/vidux` while still loading `/pilot-leo` for Leo-specific boundaries.
- The ledger command uses the current `ledger-emit.sh --help` surface verified on 2026-06-01.
