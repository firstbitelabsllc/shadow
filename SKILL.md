---
name: shadow
description: "Chief-of-staff briefing, durable plan/proof/resume, and bounded native-host execution for AI coding work."
---

# Shadow

Use Shadow when work must survive sessions, hosts, or interruptions and a
cold reader should know the Outcome, current move, proof, and next decision.

Skip it for a factual answer or an obvious one-step edit with no handoff.

## How Shadow works

Standing behavior for every session rides in `AGENT.md` at this skill's root;
the file grammar is `docs/reference/grammar.md`, enforced by
`scripts/shadow-lint.py`. Follow both: declare a mode (explore or ship) as
the first move of a cycle, run `shadow lint` before honoring a mode flip,
write plans as you execute, and ship only through proof lines per DoD
clause. The eight core concepts and the two questions (why now? what does
this contradict?) are the process law; the sections below are the delegation
and proof mechanics underneath them.

## Worklane boundary

Shadow supports the project currently being worked on; it is not a global
gate for every project. Its own open proof must not stop another product from
shipping the highest-value reachable row in that product's canonical plan.
“One bounded task” keeps a handoff reviewable—it does not make the fleet
single-threaded or defer safe, obvious in-scope improvement.

## Start every cycle

1. Read repository instructions and the repository-owned `PLAN.md`.
2. Inspect the exact Git revision, worktree state, and proof named by the plan.
3. Resume an in-progress item; otherwise take the highest unblocked item.
4. Make one bounded, reversible change and run the real repository gate.
5. Record result, proof, uncertainty, and one exact resume move in `PLAN.md`.

Never overwrite unexplained work or create a second queue. A commit, worker
message, or receipt is not acceptance proof by itself.

## Delegate one task

Use the active host directly for normal work. For a bounded handoff, use:

```bash
shadow host run --host codex|claude-code|cursor \
  --repo <exact-clean-worktree> --task-file <frozen-task> --task-id <id> \
  --allowed-path <exact-path> \
  --out <project>/.shadow/evidence/<id>.json
```

The task file is frozen, the worktree must be clean, allowed paths are exact,
and the host must emit one bounded receipt with passing tests. Which provider
or account the host uses is the host CLI's own business — Shadow passes no
selector and records none.

Review the diff and reproduce important tests before accepting the result.
Do not put credentials, prompts, transcripts, private paths, or provider output
in a task receipt.

## Flip a task

`shadow accept --row ~hash --repo <project>` is the only code path that flips
a task to completed: it reruns the task's `cmd` proof in a detached clean
checkout of HEAD and, only on a pass, rewrites the task and appends its
paired PROOF line in one commit carrying `PLAN.md` alone. `read` and `gate`
proofs are person judgments — re-observe them yourself and append the PROOF
line with the flip.

## Goal chaining

A goal is never allowed to simply end. When a goal condition is met, parks,
or is superseded, the SAME closeout must:

1. append the successor pointer to the owning PLAN.md — one row naming the
   next Outcome and its exact resume move (or none-mission-complete with the
   evidence line);
2. when successor work exists, hand the person the next /goal text ready to
   paste — the chain carries continuity, not the person memory;
3. leave no in-flight background work (builds, sweeps, collectors) ownerless:
   the successor names each one and its completion predicate.

A goal that ends without its pointer is an incomplete cycle, exactly like a
worktree left standing after LAND.

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

Shadow owns one product identity, one `PLAN.md` authority, and one bounded
project-local evidence path. Native Codex, Claude Code, and Cursor own model
authentication and execution. Do not add a router, daemon, scheduler, cloud
executor, credential relay, transcript store, or parallel status database.
Thermo and Ponytail remain separate review disciplines rather than runtime
roles.
