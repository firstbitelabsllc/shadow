---
name: shadow
description: "Use when work must survive sessions, hosts, or interruptions and needs one durable plan, proof, resume path, or chief-of-staff brief. Skip factual answers and obvious one-step edits with no handoff."
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
2. Read the selected entity's repository instructions and its local plan under
   `~/.shadow/plans/` (or a product's declared release plan), then inspect the
   relevant source revision, worktree state, and named proof.
3. Resume every checkpoint owned by that seat; otherwise atomically claim the
   highest reachable checkpoint and fan out path-disjoint claims when useful.
4. Drive claimed lanes to recorded results and run their real repository gates.
5. Record each result, proof, uncertainty, blocked wake, and reachable
   successor in `PLAN.md`.
6. Continue until the Outcome is mechanically accepted or every remaining row
   is behind an exact hard rail.

A direct read-only question about the seat's current work is not an execution
cycle. Answer from the first current bounded view, then stop: do not materialize
the plan, call `shadow amp`, reread status for the footer, or start work unless
the person asked to resume or act.

Never overwrite unexplained work or create a second queue. A commit, worker
message, or receipt is not acceptance proof by itself.

## Shape a goal

`plugins/shadow/skills/amplify/SKILL.md` owns goal shaping. The one standing Shadow goal remains
unchanged and skill-free. A specific goal is normally four lines and at most 80
words: outcome, resume, proof, and `Skills:` with one to four canonical names
resolved from the current local catalog. Broad intent compiles into the owning
`PLAN.md`; its full tool roster, inventories, matrices, sequencing, fallbacks,
and standing policy stay there. Fold a request-specific boundary into outcome
or proof rather than adding a fifth line. Shortening the pointer must never
narrow the outcome. Quantify only when the number changes a decision. Counts of
tasks, agents, commits, tests, or artifacts are receipts, not goal success.

`shadow throw --repo <project> --task '~id' --by <seat>` atomically claims the
checkpoint and returns its deterministic starting block. `shadow amp` resumes
only a checkpoint the named seat already owns. The block points at the entity
plan — committed ref, checkpoint, proof, and milestone capabilities — within
one paste budget. Put any new durable requirement from the conversation in the
owning `PLAN.md` in the same move or it did not happen.

When the request is a loose steer rather than a task ("use adversaries", "dial
in jordan mode", "focus on details"), translate it with
`plugins/shadow/skills/amplify/references/amplify.md` — the steer-to-mechanism table, the filler
test, and the rule that every mechanism gets a proof that can refuse it.

`shadow goal` prints the static standing goal for a host's instruction file.
That text never changes; only what the plans point at does.

## Delegate claimed work

Use the active host directly for normal work. For each claimed handoff, use:

```bash
shadow host run --host codex|claude-code|cursor|grok \
  --work-class planning|coding|review|lightweight \
  --delegation direct|required \
  --repo <exact-clean-worktree> --task-file <frozen-task> --task-id <id> \
  --allowed-path <exact-path> \
  --out <project>/.shadow/evidence/<id>.json
```

The task file is frozen, the worktree must be clean, allowed paths are exact,
and the host must emit a scoped receipt with passing tests. The lead chooses
the host, semantic work class, and explicit execution shape; Shadow
deterministically supplies that pair's native model selector and enables or
disables the verified native child door. `required` fails closed on Cursor
until its headless CLI exposes observable child lineage. The host CLI still
owns authentication, account choice, quota, and provider execution. Requested
model and observed model are distinct: the private attempt records the former,
while observed-model and child-lineage proof require the owner-local gauntlet
documented in `docs/reference/execution-policy.md`.

Review the diff and reproduce important tests before accepting the result.
Do not put credentials, prompts, transcripts, private paths, or provider output
in a task receipt.

## Flip a task

`shadow accept --row '~hash' --repo <project> --by <seat>` is the only code path that flips
a source-backed task to completed: it reruns the task's `cmd` proof in a
detached clean checkout of HEAD and, only on a pass, rewrites the source plan
and appends its paired PROOF line. Infrastructure plans remain local under
`~/.shadow/plans/` and are never committed. `read` and `gate`
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
before/after pair; a flow gets a small diagram; a fact gets one line —
the Brief contract itself demands these; when the `taste` slot is filled,
its binding names the visual owner rather than improvising the format. In a
terminal host, a fenced mermaid block is source code, not an explanation —
anything denser than a text tree or diff renders as one focused HTML file
opened for the person:

```
BEFORE                       AFTER
credential says "Alice"      credential says "Alice"
claim("Bob") -> ALLOWED      claim("Bob") -> REFUSED 403
```

A PR number, plan slug, file path, or symbol name is a reference, never an
explanation. Never send an A/B/C whose subject was not explained in that same
message, and never re-send an option the person has ignored — repetition means
the framing failed, so rewrite it.

Every Shadow chat response ends with a compact `Ongoing tasks` projection. Read
`shadow status --in-flight --json` at send time for live claims, then read
`shadow status --by <seat>` for one bounded next move. Do not load the
full-portfolio `shadow status --json` surface into the conversation. List live
claims first with project/outcome, checkpoint, owner, state, proof, and the
next exact wake or command. When the seat owns no claim and its bounded view
exposes a reachable checkpoint, list exactly that checkpoint under `Next`.
This projection does not enumerate every reachable or waiting row, so never
imply that unseen work is absent. Print `Active tasks: none` only when the
fresh in-flight projection has no live claims. This is a view of the computer
board, never a second queue: do not hard-code stale state or expose private
paths, provider/account data, or chat-only work.

The direct read-only current-work case above is the narrow exception: its first
current bounded view is already the projection, so the concise answer ends the
turn without another board read or a routine footer.

Hide implementation detail unless it changes the decision. The browser is a
loopback projection of the computer board joined to entity plans; it never
becomes authority.

## Extensions

Shadow declares named extensions its method assumes it can reach — memory for
routed recall (a lead, never plan, proof, or ownership authority) and taste
for the finished-quality grade and the voice of everything written for
humans — in `docs/reference/slots.md`. `shadow slots` reports which are
filled. Shadow runs correctly with every one empty: a slot never gates a
cycle, claims a row, or carries proof, and no plan verb reads it. No slot
asserts anything about tooling Shadow does not call: which memory backend
you run is your own configuration, the same boundary `config.md` draws
around which provider a native host uses.

## Boundaries

Shadow owns a single product identity and one authority hierarchy: the
per-computer root board for coordination, entity `PLAN.md` files for milestone
and checkpoint detail/proof, and project-local evidence paths. Native Codex,
Claude Code, Cursor, and Grok own model authentication and execution. Shadow's
four semantic work classes plus `direct|required` are a deterministic execution
policy, not a prompt classifier or scheduler. Do not add a router, daemon, scheduler, cloud
executor, credential relay, transcript store,
or parallel status database.
Thermo and Ponytail remain separate review disciplines rather than runtime
roles.

## Acceptance

Shadow is accepted only when a cold seat can recover the one authority, resume
owned work, and run proof that could reject a plausible shallow result. A plan
write, claim, commit, passing command, merge, install, live surface, and
person-observed outcome remain distinct receipts.
