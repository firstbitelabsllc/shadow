---
name: shadow
description: "Chief-of-staff briefing, durable plan/proof/resume, local role routing, and bounded native-host execution for AI coding work."
---

# Shadow

Use Shadow when work must survive sessions, hosts, or interruptions and a
cold reader should know the Outcome, current move, proof, and next decision.

Skip it for a factual answer or an obvious one-step edit with no handoff.

## The Method

Standing behavior for every session rides in `AGENT.md` at this skill's root;
the file contract (entity/milestone/checkpoint grammar, PLAN-LINT, the Close
coverage matrix and lesson delta, steering) is `docs/reference/method.md`.
Follow both: declare a mode (Spike, Defer, Challenge, or Close) as the first
move of a cycle, run PLAN-LINT before honoring a mode transition, write plans
as you execute, and close only through the DoD coverage matrix. Modes and the
adversarial gate are the process law; the sections below are the delegation
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
shadow route \
  --repo <exact-clean-worktree> --task-file <frozen-task> --task-id <id> \
  --task-kind plan|hard-dev|dev|debug|review|lead \
  --out <project>/.shadow/evidence/<id>.route.json

shadow host run --host codex|claude-code|cursor \
  --repo <exact-clean-worktree> --task-file <frozen-task> --task-id <id> \
  --allowed-path <exact-path> \
  --route-file <project>/.shadow/evidence/<id>.route.json \
  --out <project>/.shadow/evidence/<id>.json
```

`route` prints one generic local role/native-host choice, same-role
alternatives, and one escalation condition; it never launches the host or
silently substitutes one. A host run with `--route-file` verifies the frozen
task, local roster revision, and selected host before launch.

Review the diff and reproduce important tests before accepting the result.
Do not put credentials, prompts, transcripts, private paths, or provider output
in a task receipt.

## Drive a small batch

When a single project has up to three clearly separate, ready pieces of work,
put one typed Drive Packet in that same project's `PLAN.md`. Start with:

```bash
shadow drive prepare --repo <exact-clean-worktree>
```

Preparation picks only path-disjoint work with distinct already-declared native
hosts and starts nothing. It writes a frozen local session. Start work only
with the explicit foreground action:

```bash
shadow drive launch --repo <exact-clean-worktree> --session <session-id>
```

Launch rechecks the plan and Git revision, creates isolated worktrees, invokes
the sealed native-host contract, reruns the plan's local proof command, and
commits green results to kept review branches. It does not push, open a PR,
deploy, publish, spend, delete worktrees, retry, or silently choose a different
host. Treat failed lanes as a clear next move, not a reason to stop unrelated
reachable work.

If every lane is green, the lead may take one separate explicit local step:

```bash
shadow drive accept --repo <exact-clean-worktree> --session <session-id>
```

Acceptance reruns each named proof in a separate clean lead checkout, then
creates one local Git merge commit in that project. It does not push, open a
pull request, deploy, publish, spend, delete, or contact another computer.

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
authentication and execution. A foreground, explainable router and explicitly
started Drive session are allowed; do not add an autonomous router, daemon,
scheduler, cloud executor, credential relay, transcript store, or parallel
status database. Thermo and Ponytail remain separate review disciplines rather
than runtime roles.
