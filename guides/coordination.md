# Concurrent-runner coordination

Vidux keeps durable work truth in the Authority `PLAN.md` and stores only
short-lived ownership and resume metadata in a local claims journal. It does
not create chats, invoke providers, schedule goals, or preempt an active owner.

Before editing, a runner fresh-reads the plan and claims one exact work surface:

```bash
vidux coordinate claim \
  --repo resplit-ios \
  --claim 'Sources/ReceiptCurrencyView.swift' \
  --owner codex-task-1 \
  --lane receipt-currency \
  --plan-path "$PWD/.cursor/plans/resplit-2.0-asc-pipeline.plan.md" \
  --task-id currency-pill-routing
```

Use the returned `claim_id` for renewals and durable resume checkpoints:

```bash
vidux coordinate heartbeat --claim-id clm_example --owner codex-task-1
vidux coordinate checkpoint \
  --claim-id clm_example \
  --owner codex-task-1 \
  --summary 'routing code and focused test written' \
  --resume 'run the receipt-currency simulator journey, then update the PLAN row' \
  --proof 'git diff --check'
```

On a confirmed usage-window failure, release immediately with a resume pointer:

```bash
vidux coordinate release \
  --claim-id clm_example \
  --owner codex-task-1 \
  --status usage_exhausted \
  --resume 'open the PLAN row, inspect the worktree diff, then run focused tests'
```

`vidux coordinate snapshot --repo resplit-ios` returns active owners plus
recent resumable handoffs. A conflicting live lease means stand down and claim
different work. An expired lease permits a new claim only after the new runner
verifies the plan, worktree, diff, PR, build/runtime state, and proof. Source
edited, branch pushed, PR merged, build uploaded, and live runtime remain
separate truths.

The browser's **Live work** panel is a read-only, exact-plan projection of the
same journal. Hostnames, process ids, journal paths, secrets, and provider
identity never cross that HTTP boundary.
