---
name: shadow
description: "Chief-of-staff briefing, durable plan/proof/resume, and proactive parallel native-host execution for AI coding work."
---

# Shadow

Use Shadow when work must survive sessions, hosts, or interruptions and a
cold reader should know the Outcome, active lanes, proof, and reachable
successors.

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

Shadow supports every claimed lane needed by the current Outcome; its own open
proof must not stop another product from shipping reachable work in that
product's canonical plan. Drain the reachable queue, fan out safe path-disjoint
claims, integrate proof, and keep choosing successors. A checkpoint boundary protects
ownership and reviewability; it is never a session, campaign, or ambition cap.

## Start every cycle

1. Establish one stable public seat name and run `shadow status --by <seat>`;
   the computer board supplies global priority, ownership, entity pointers,
   and resume from any directory.
2. Read the selected entity's repository instructions and committed `PLAN.md`,
   then inspect its exact Git revision, worktree state, and named proof.
3. Resume every checkpoint owned by that seat; otherwise atomically claim the
   highest reachable checkpoint and fan out path-disjoint claims when useful.
4. Drive claimed lanes to recorded results and run their real repository gates.
5. Record each result, proof, uncertainty, blocked wake, and reachable
   successor in `PLAN.md`.
6. Continue until the Outcome is mechanically accepted or every remaining row
   is behind an exact hard rail.

Never overwrite unexplained work or create a second queue. A commit, worker
message, or receipt is not acceptance proof by itself.

## Shape a goal

A loose ask becomes a complete executable goal brief before it becomes plan
rows. Gather what makes the full outcome executable (the owning `PLAN.md`,
active claims, reachable work, git state, and named files/errors/surfaces).
Synthesize, then cut filler, duplicate policy, invented phases, and vague
"improve everything" wording without an acceptance matrix. Never translate
"everything", "end to end", "all boats rise", or equivalent outcome language
into a single task, slice, or campaign.
Deliver the goal ready to paste:

```text
Outcome: <plain result>.
Authority: <computer board revision for coordination> + <entity PLAN.md at committed ref>.
Resume: <all checkpoints owned by this stable seat, then ranked reachable checkpoints>.
Scope: <every surface required by the Outcome>; do not touch <prohibited paths>.
Proof: <focused checks per lane>, <affected integration>, <real surfaces>.
Policy: the computer board owns project priority, entity pointers, claims,
owners, and resume; each entity PLAN.md owns milestones, checkpoints, detail,
and proof. Park blockers with exact wakes and continue every reachable
checkpoint; stop only when full acceptance is mechanically true or every
remainder is hard-rail blocked.
```

Quality gate before delivery: a fresh session could start without asking
what the task means; every line changes an implementation or safety
decision; "done", "merged", "live", and "proven" stay distinct; the brief
is shorter than the context it replaces.

`shadow throw --repo <project> --task '~id' --by <seat>` atomically claims the
checkpoint and returns its deterministic starting block. `shadow amp` resumes
only a checkpoint the named seat already owns. The block points at the entity
plan — committed ref, checkpoint, proof, and milestone capabilities — within
one paste budget. Put any new durable requirement from the conversation in the
owning `PLAN.md` in the same move or it did not happen.

When the request is a loose steer rather than a task ("use adversaries", "dial
in jordan mode", "focus on details"), translate it with
`skills/goal/references/amplify.md` — the steer-to-mechanism table, the filler
test, and the rule that every mechanism gets a proof that can refuse it.

`shadow goal` prints the static standing goal for a host's instruction file.
That text never changes; only what the plans point at does.

## Delegate claimed work

Use the active host directly for normal work. For each claimed handoff, use:

```bash
shadow host run --host codex|claude-code|cursor \
  --repo <exact-clean-worktree> --task-file <frozen-task> --task-id <id> \
  --allowed-path <exact-path> \
  --out <project>/.shadow/evidence/<id>.json
```

The task file is frozen, the worktree must be clean, allowed paths are exact,
and the host must emit a scoped receipt with passing tests. Which provider
or account the host uses is the host CLI's own business — Shadow passes no
selector and records none.

Review the diff and reproduce important tests before accepting the result.
Do not put credentials, prompts, transcripts, private paths, or provider output
in a task receipt.

## Flip a task

`shadow accept --row '~hash' --repo <project> --by <seat>` is the only code path that flips
a task to completed: it reruns the task's `cmd` proof in a detached clean
checkout of HEAD and, only on a pass, rewrites the task and appends its
paired PROOF line in one commit carrying `PLAN.md` alone. `read` and `gate`
proofs are person judgments — re-observe them yourself and append the PROOF
line with the flip.

## Goal chaining

A goal is never allowed to simply end. When a goal condition is met, parks,
or is superseded, the SAME closeout must:

1. append a successor pointer row to the owning PLAN.md naming the next
   Outcome and its reachable start set (or none-mission-complete with the
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

Explain every term in the same message that uses it. A change gets a
before/after pair; a flow gets a small diagram; a fact gets one line:

```
BEFORE                       AFTER
credential says "Alice"      credential says "Alice"
claim("Bob") -> ALLOWED      claim("Bob") -> REFUSED 403
```

A PR number, plan slug, file path, or symbol name is a reference, never an
explanation. Never send an A/B/C whose subject was not explained in that same
message, and never re-send an option the person has ignored — repetition means
the framing failed, so rewrite it.

Hide implementation detail unless it changes the decision. The browser is a
loopback projection of the computer board joined to entity plans; it never
becomes authority.

## Extension buckets

Shadow declares named slots its method assumes it can reach — superpowers for
how each claimed lane is worked, taste for the finished-quality grade, honcho for durable
memory — in `docs/reference/buckets.md`. `shadow buckets` reports which are
filled. Shadow runs correctly with every one empty: a bucket never gates a
cycle, claims a row, or carries proof, and no plan verb reads it.

## Boundaries

Shadow owns a single product identity and one authority hierarchy: the
per-computer root board for coordination, entity `PLAN.md` files for milestone
and checkpoint detail/proof, and project-local evidence paths. Native Codex,
Claude Code, and Cursor own model authentication and execution. Do not add a
router, daemon, scheduler, cloud executor, credential relay, transcript store,
or parallel status database.
Thermo and Ponytail remain separate review disciplines rather than runtime
roles.
