---
name: pilot-puppy
description: "Chief-of-staff briefing, durable plan/proof/resume, and bounded native-host execution for AI coding work."
---

# Pilot Puppy

Use Pilot Puppy when work must survive sessions, hosts, or interruptions and a
cold reader should know the Outcome, current move, proof, and next decision.

Skip it for a factual answer or an obvious one-step edit with no handoff.

## Start every cycle

1. Read repository instructions and the repository-owned `PLAN.md`.
2. Inspect the exact Git revision, worktree state, and proof named by the plan.
3. Resume an in-progress item; otherwise take the highest unblocked item.
4. Make one bounded, reversible change and run the real repository gate.
5. Record result, proof, uncertainty, and one exact resume move in `PLAN.md`.

Never overwrite unexplained work or create a second queue. A commit, worker
message, or receipt is not acceptance proof by itself.

## Drive one task

Use the active host directly for normal work. For a bounded handoff, use:

```bash
pilot-puppy host run --host codex|claude-code|cursor \
  --repo <exact-clean-worktree> --task-file <frozen-task> --task-id <id> \
  --allowed-path <exact-path> --out <project>/.pilot-puppy/evidence/<id>.json
```

Review the diff and reproduce important tests before accepting the result.
Do not put credentials, prompts, transcripts, private paths, or provider output
in a task receipt.

## Brief the person

Lead with:

- Outcome
- What changed
- What is happening now
- Proof or uncertainty
- The one decision needed, expressed as at most A/B/C

Hide implementation detail unless it changes the decision. The browser is a
loopback projection of the same plan; Markdown remains authority.

## Boundaries

Pilot Puppy owns one product identity, one `PLAN.md` authority, and one bounded
project-local evidence path. Native Codex, Claude Code, and Cursor own model
authentication and execution. Do not add a router, daemon, scheduler, cloud
executor, credential relay, transcript store, or parallel status database.
