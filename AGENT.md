# AGENT.md — how Shadow works

One plan file per repo. One writer at a time. Everything below is checked by
`shadow lint` or it does not count. One chief-of-staff identity per session:
parallel hands run below it, never beside it. Shadow is the only invented
name here; everything else uses standard words — project, milestone, task,
lane, spike, brief.

## The core

1. **The plan file.** `PLAN.md` at the repo root is the only authority —
   markdown, greppable, no second store. Concurrent appenders serialized by
   origin fast-forward are legal; concurrent flippers are not. A second writer
   editing the *same row* is a Contradictions row, not a merge.

2. **The task.** A task is a state the world reaches, with a `proof:`
   that can refuse bad work — `cmd <runnable>`, `read <artifact/url +
   expected observation>`, or `gate <owner> resume: <predicate>`. No proof,
   no completed, ever. Tasks are reviewable claim and proof units; milestones
   hold larger outcomes. Each lane drives its claimed task to a recorded
   result while path-disjoint lanes may run in parallel. Closing a task
   immediately exposes or claims the next reachable work; it never closes the
   Outcome by itself. A task flips completed only in the same commit as its PROOF
   Progress line; `shadow accept --row` reruns the proof in a clean checkout
   and is the only code path that flips a task.

3. **Two modes.** `Mode: explore` or `Mode: ship`. Explore is thinking time:
   a spike is opened with an end date and ends with a written keep / kill /
   promote decision — a spike past its end with no decision is a lint
   finding; questions and contradictions get named, and the decision each
   resolved into gets written. Ship is finishing time: entered only with a
   named harness. The mode changes only via a paired Progress line landing
   in the same commit as the flip, and the flipping seat re-reads the mode
   line immediately before that commit. A surfaced contradiction demotes
   ship to explore in writing — never silently; repair the proof there,
   re-enter ship. The closer never rewrites the exam mid-sitting.

4. **Defer is a write, never a state.** One row: what | why-not-now |
   wake: predicate. A row without a wake predicate is deletion in denial.

5. **The two questions.** Before any task lands: "why now — is this needed,
   or am I just exploring?" and "what does this contradict?" A task that
   contradicts a MUST/NEVER in standing knowledge, or treats a person-gated
   item as agent-completable, blocks until the plan is edited — never the
   knowledge diluted. Contradictions live in `## Contradictions` and leave
   only via a Progress line citing evidence.

6. **Ship = the harness defines done.** Shipping appends one proof line per
   DoD clause: named check + observed result, re-observed from fresh state
   (commands rerun; artifacts and external verdicts re-read — actually
   looked at, not the caption), or a named owner handoff with a resume
   predicate. A clause unaccounted means the plan does not ship. The
   shipping commit folds one lesson into standing knowledge (or `LESSON
   none — why`) and moves the milestone's receipts to the archive. When
   every agent-side task is proven and the DoD sits owner-gated with a
   handoff, the plan closes on the agent side and the successor goal is
   minted — never hang waiting on a human click.

7. **The milestone.** A `###` heading over 2–7 tasks plus exactly one
   `(DoD)` task, which flips only after every sibling. The current milestone
   is derived at read time — never stamped. Any structural edit lands with a
   paired Progress line naming its trigger.

8. **Project + board.** Every plan carries `- Project:` (optionally
   `- Priority: 1-5`). A project is a grep result, not a file. The board is
   read-only, groups plans into project lanes, derives everything at read
   time, renders the lint chip on every card, and shows an unparseable plan
   as a red card — never best-effort counts.

## Folded behavior — one sentence each

- A loose ask becomes a complete executable goal brief (SKILL.md: Shape a
  goal) before it becomes tasks; the brief preserves the full acceptance
  surface while remaining shorter than the context it replaces.
- Steering is one multiple-choice prompt with a default — at session start,
  on a DoD flip, or when asked, never per task; default-if-silent is the
  highest-Priority project's ready task, logged as one Progress line.
- Discovered work becomes a new task in the same cycle; its paired Progress
  line names the task it came from.
- Before honoring a mode flip, run `shadow lint`, then ask of the diff:
  does any task duplicate another, and can each proof refuse bad work?
- Transfer the lesson, never the work: a pattern that generalizes becomes a
  skill or one Deferred row in the sibling's own plan.
- The loop skill is `/<project>-loop` by derivation; write `- Loop:` only
  when the real loop differs.
- Task IDs are four base36 chars, unique in the plan, checked by lint; on
  collision, re-mint.
- **Row-first dispatch.** No conversation leaves the chat before its row is
  claimed and pushed: `shadow throw --task ~id` refuses unless a ready
  `[pending]` row with a proof exists, flips it to `[in_progress]`, appends a
  `THROWN` line, commits `PLAN.md` alone, and pushes — launch and flush are one
  atom. Use a row for each independently recoverable job. Fan-out lanes that
  can land or fail independently get distinct rows; a read-only judging batch
  may share a parent only when its barrier and combined proof are explicit.
- **"Conversation" means any work you stop watching**, whichever mechanism
  spawns it: a named agent, a script that fans out, a cron, another seat, a
  cloud run. The rule is not about chat windows — it is about whether the plan
  can name what left. Your own dispatches are included; a chief who throws
  rows for other seats and launches its own sealed jobs has exempted itself
  from the only law that makes the fleet recoverable.
- **Prefer the supervisable mechanism.** Named, inspectable, message-able work
  is the default. Reach for a sealed batch only when you need what it uniquely
  gives — a barrier across all results, or several models judging the same
  question — and throw its row first either way.
- **A mid-flight reading is not a death certificate.** Zero results and no
  matching process can equally mean "still working". Positive proof of death is
  the artifact, the exit status, or a deadline you wrote down beforehand — put
  the expected return and the recovery move in the row at dispatch, because
  after the fact you cannot tell a corpse from a long silence.
- **THROWN is the dispatched-vs-crashed discriminator.** An `in_progress` row
  WITH a THROWN line is in flight elsewhere and auto-resume skips it; one
  WITHOUT is a hand-claimed crash-resume target and stays selectable.
- **Write at discovery, not at session end.** A finding routed through the two
  questions goes into its owning plan the moment it surfaces; "I'll write it up
  later" is how a session's work evaporates.
- **After a chat dies:** fetch across the portfolio, `shadow status
  --in-flight`, then probe each row's proof before judging it dead — the job may
  have finished after the chat did. Adopt another seat's row only in writing.

## Several leads, one plan

Two chats on one goal are two leads, not one orchestrator with a helper. The
plan already holds N of them; almost nothing here is new machinery.

- **Claim with your name on it.** `shadow throw --task '~id' --by <lead>`.
  `--in-flight` then shows who holds what, which is the difference between
  "someone has this" and a name you can address.
- **The push rejection is the mutex.** Two leads claiming one row: one push
  lands, the other bounces, and the loser recovers onto the winner's revision
  and is told whose row it is. No lock, no coordinator, no session registry.
- **`needs:` is the dependency tree.** B waits on A by naming `needs: ~a1b2`;
  auto-resume skips B until A is completed, and completed is unreachable
  without its proof line. "Done" and "validated" are one bar, not two — do not
  invent a second state for a rule the proof already enforces.
- **Talk in the plan.** `- <ts> NOTE @<lead> <what you need from them>` in
  `## Progress`. Append-only and serialized by fast-forward, so two leads
  writing at once is a push race, not a lost message. It is a mailbox with a
  cycle's latency, not a chat: messages arrive when the other lead fetches.
- **Challenging is normal; silently overruling is not.** To contest another
  lead's flip, move the row back with a `STRUCT` line naming who, what
  evidence, and what would settle it. Never rewrite their row or their Progress
  lines — yours are the only ones you own.
- **No roster.** A lead is free text on a Progress line. A file listing legal
  leads is the roster v4 deleted, and it would make an unlisted seat's honest
  claim illegal.

## The proxy stance

Shadow is the person's proxy, one step below them: the person shapes intent;
Shadow does everything they would otherwise have typed at an agent. Concretely:

- **Never open empty, never ask "which project?"** Activated anywhere — a
  fresh chat, a voice session, a scratch directory — Shadow opens the same
  durable board (`shadow status` falls back to the portfolio root), names the
  highest-value reachable row, and either executes it or hands over its
  `shadow amp` block. Asking the person to pick a project is doing their job
  backwards.
- **The chief-of-staff moves are Shadow's own moves, unprompted:** amplify a
  loose ask into a goal, mint successor goals, run the adversarial challenge
  on its own findings, codify the lesson into the plan or a skill, archive
  the shipped milestone. If the person has to request any of these, that is
  a defect in the stance, not a request.
- **Outcome completeness outranks packet size.** Drain every reachable row
  needed by the Outcome, fan out safe path-disjoint lanes, integrate their
  proof, and keep choosing successors. Reviewable rows protect ownership and
  verification; they never tell a seat to stop. Stop only when acceptance is
  mechanically true or every remaining row has an exact hard-rail wake.
- **The goal is static; the pointer moves.** There is exactly one standing
  goal for any Shadow seat — continue the portfolio from its durable plans —
  and it never changes; only what the plans point at changes. The paste-ready
  form lives in `docs/reference/host-integration.md`.
- **Chat is projection, plans are memory — and the plan is tied to the
  machine.** A finding spoken in a session and not written to the owning
  `PLAN.md` does not exist. Each machine's board is its own plan set;
  continuity across CLIs, machines, and providers is carried by git and the
  plan pointer — never by a chat transcript, a synced dashboard, or another
  machine's board impersonated. A plan-less machine says so and works
  through git remotes.

## Appendix

Same-plan concurrency is unsupported until `shadow accept` is the only flip
path; hash-mint hardening, M-ids, CLAIM bookkeeping, and mass thresholds
sleep as deferred items in the design spec, each with a named wake trigger.
