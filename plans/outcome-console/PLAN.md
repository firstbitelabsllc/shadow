# Outcome Console Plan

**Parent authority:** [`../../PLAN.md`](../../PLAN.md)
**Status:** provider-neutral interchange plus a local Outcome/Steer/proof
prototype implemented; exceptional Ask dogfood and live Steer application
remain

## Outcome

Make ordinary software work feel obvious to someone who is not asking for
implementation details. They state an outcome, receive a concise grounded
answer, and steer the work without assembling an agent stack, choosing models,
reading code, or managing a fleet.

The product should make the routine path boring: choose a sensible, explainable
recipe; keep the work safe; and interrupt only for a real product choice,
security boundary, money, external communication, or irreversible action. A
plan remains mandatory underneath, but it is a reliability mechanism, not an
interface the person must learn.

## Opportunity Decision

Proceed with a narrow Outcome Console, not a general coding-agent GUI.

The opportunity is not “chat that can write software”; capable products already
offer that. The wedge is that one durable Outcome survives chats and workers,
ordinary execution requires no approval ritual, a Steer replaces stale
direction in place, and an Ask appears only for a genuine fork. The user sees
proof without having to watch the machinery.

The product hypothesis is that a non-coder can direct the routine build, fix,
and release loop from intent and evidence. It does not mean the system hides
uncertainty, skips engineering proof, or silently crosses a hard safety
boundary.

Stop this direction if dogfood shows that people primarily want a code editor,
agent selector, editable prompt queue, or plan-approval screen. Those are
crowded products and would pull Vidux away from its plan/proof/resume strength.

## Market Evidence

This is an initial official-documentation snapshot, not a market-size claim.

- [Lovable Agent mode](https://docs.lovable.dev/features/agent-mode) makes
  agent steps, files, diffs, queued messages, stop, and undo visible.
- [Lovable Plan mode](https://docs.lovable.dev/features/plan-mode) asks the user
  to review and approve an editable plan before implementation.
- [Replit Agent](https://docs.replit.com/features/agent/overview) already
  promises plain-language app creation with no coding required, while
  [Plan mode](https://docs.replit.com/features/agent/plan-mode) and the
  [task board](https://docs.replit.com/features/agent/task-board) expose plan
  review and task management.
- [Replit checkpoints](https://docs.replit.com/features/version-control/checkpoints-and-rollbacks)
  expose change history and rollback as explicit controls.
- [OpenHands conversation goals](https://docs.openhands.dev/sdk/guides/agent-server/conversation-goals)
  keep a goal on the same conversation and support progress plus stop/resume.
- [OpenHands security](https://docs.openhands.dev/sdk/guides/security) exposes
  confirmation policy and risk analysis as execution controls.

These products validate goals, progress, interruption, and safety controls.
They do not by themselves validate the Outcome Console's proposed
differentiation. The testable bet is that a non-coder values less operational
interface: one Outcome, one exceptional Ask, one Steer surface, and proof when
finished.

## Product Contract

### What enters

- A plain-language **Outcome**, **question**, or **Steer** by text today and by
  voice when the same contract has a safe typed fallback.
- Optional current project or plan context. The person should not need to name
  a repository when the active context already makes it clear.

### What comes back

- A short, grounded brief: what is happening, what is blocked, what happens
  next, and the one decision that genuinely needs the person.
- An explicit Steer lifecycle: **received**, **applied**, **working**,
  **blocked**, **finished with proof**, or **not delivered**.
- An openable proof or plan reference when someone wants detail; never a forced
  code, terminal, provider, or fleet dashboard.

### What stays underneath

- Vidux remains the plan, evidence, ownership, checkpoint, and cleanup kernel.
- The native coding host remains responsible for selecting providers,
  dispatching workers, editing code, testing, and publishing results.
- A conversation is a reference to an independent context, never a claim that
  every chat shares memory or that raw transcripts are the source of truth.
- One Outcome may coordinate many project and worker threads, but those threads
  remain independently owned and do not become competing user-visible queues.

## Smallest Useful GUI

The default home is one calm Outcome card:

1. **Outcome** — one plain sentence naming the result.
2. **State** — **working now**, **needs you**, or **finished with proof**.
3. **Current move** — one sentence describing what is actually happening next.
4. **Steer** — one composer that updates this same Outcome.
5. **Ask** — absent by default; when present, one real fork with concise options
   and consequences.
6. **Proof** — a compact receipt or link, opened only when wanted.

There is no mode switch between planning and execution on this screen. There is
no prompt queue, approval button for routine work, model picker, worker list,
terminal, file tree, or token dashboard. Stop and resume are lifecycle actions,
not an invitation to manage a fleet.

An Ask is a decision interrupt, never a disguised “run” button. A Steer is not
another queued prompt: once applied, stale direction is visibly superseded and
must not continue executing.

## Semantic Contract

The provider-neutral boundary is deliberately small:

- **Outcome:** stable identity, plain-language result, current state, current
  move, optional open Ask, and zero or more proof references.
- **Steer:** stable identity, Outcome identity, bounded instruction summary,
  lifecycle state, and acknowledgment/proof reference.
- **Ask:** stable identity, one allowed fork category, one concise question,
  bounded options with consequences, and open/answered/superseded state.
- **Proof reference:** truthful type, location, verification summary, and
  delivered/not-delivered state. It is evidence, not a second plan.

Raw transcripts, provider prompts, secrets, and untrusted retrieved text never
become this state. The coding host may derive a bounded semantic summary, but
the durable plan and audit receipt remain the authority.

## Default Recipe Boundary

Recipes are versioned, tested defaults for common work—not a large prompt that
reasons from first principles every time, and not a configuration studio.

The initial recipe families are:

1. **Build or change a product feature** — scope, data contract, UI, validation,
   tests, and rollback.
2. **Add identity or access** — the project’s established authentication
   pattern, least-privilege boundaries, and negative-path proof.
3. **Add data or a service integration** — schema/migration safety, staging
   environment, secrets boundary, monitoring, and recovery.
4. **Add payments** — provider-safe integration, test-mode proof, and no live
   charge or publishing action without explicit authority.
5. **Fix a bug** — reproduction, system context, smallest reversible change,
   regression proof, and parent-release linkage.
6. **Ship a release** — release notes, required checks, staged validation, and
   a truthful shipped/not-shipped receipt.

Each recipe may select conventional tooling when the current project already
establishes it. It must state the material tradeoff and escalate when no safe
default exists. It must not silently create accounts, spend money, publish, or
widen data access.

## Planning and Garbage Collection Contract

Recursive planning is allowed only when it gives an independent scope, proof,
or revert boundary. The hierarchy is deliberately bounded:

```
Root product plan → outcome/release plan → execution leaf
```

- Every bug gets an execution leaf, linked to the release or product outcome it
  serves. The leaf records the system context, reproduction, intended change,
  verification, owner, and close condition.
- A parent explains **why**; a leaf explains **what changes and how it is
  proved**. Parent progress derives from child terminal receipts rather than
  optimistic prose.
- No fourth planning layer without a demonstrated separate proof and revert
  boundary. Splitting files or tasks is not enough reason to deepen the tree.
- One active execution leaf owns one worktree and one claim. A worktree cannot
  outlive its leaf without an explicit handoff or extension.
- Every leaf terminates as **merged with proof**, **closed**, **handed off**, or
  **expired**. Terminal rows keep a short durable receipt; active context,
  watchers, and clean disposable worktrees are then eligible for cleanup.
- Cleanup must be visible and reversible. Never auto-delete a dirty worktree or
  user data. Report orphaned leaves, stale claims, and stale worktrees as
  attention items until their terminal state is recorded.

## Dogfood Gate

Use three non-coder dogfooders across one build, one bug-fix, and one release
scenario. A scenario passes only when the person can:

- state the Outcome without naming a repository, provider, or implementation;
- explain the current state and whether the system needs them;
- submit one Steer and see stale direction stop;
- receive zero Asks for routine work and exactly one Ask for a deliberately
  seeded genuine fork; and
- identify the final proof or honest non-delivery state without opening code,
  a terminal, a plan editor, or a worker dashboard.

Record confusion and recovery, not only task completion. The hypothesis is
falsified if a human translator is repeatedly needed, Steers behave like queued
prompts, routine work produces approval theater, or proof is not trusted.

## Ordered Work

- [completed] Record the outcome-first direction, product boundary, market
  evidence, smallest useful GUI, and bounded planning/cleanup contract.
- [completed] Carry the locally proved `outcome` / `ask` / `steer` contract
  into a provider-neutral schema, synthetic example, reference, and read-only
  validator. This deterministic proof is not live voice-loop or GUI proof.
- [completed] Build a single-screen, local-data prototype. The Outcome card,
  local Steer composer, and proof drawer are implemented and browser-proved;
  no agent, model, prompt-queue, file, or terminal controls were added.
- [pending] Add and dogfood one exceptional Ask state in the same card. It
  appears only for a genuine fork and never becomes routine approval theater.
- [pending] Run the three-person dogfood gate and record the exact places where
  status, steering, Ask frequency, or proof trust fails.
- [pending] Implement one end-to-end Steer loop against the existing plan and
  proof stores: persist acknowledgment, supersede stale direction, surface the
  lifecycle, and show linked proof or honest non-delivery.
- [pending] Add a recipe registry for the six initial families. Each recipe
  exposes its safety boundary, verification gate, and escalation triggers; it
  does not route models or execute work itself.
- [pending] Add plan-tree and worktree hygiene reporting: missing parent links,
  depth violations, stale claims, orphaned worktrees, and leaves without proof.
  Recommend cleanup before considering automation.
- [pending] Add voice only after the typed loop passes dogfood with equivalent
  lifecycle, interruption, privacy, and recovery behavior.

## Current Proof

- The market-evidence links above point to the primary product documentation
  reviewed for this hypothesis.
- `python3 tests/test_outcome_ask_steer.py` covers valid, malformed, semantic,
  privacy, size, and deterministic-output cases.
- The local browser now defaults to one Outcome card with current move, local
  Steer composer, and proof/plan details on demand. Desktop and phone
  screenshots are in `assets/vidux-dashboard.png` and `assets/vidux-mobile.png`.
- Browser proof covers the collapsed default, responsive order, local steering
  states, project drawer, technical escape hatch, and proof-plan navigation.
- Candidate proof: 22 JavaScript tests, 458 Python tests, and 136 real-browser
  flows pass across desktop, tablet, and phone; 2 Linux visual baselines are
  intentionally skipped on macOS. Docs build, the tracked-source boundary scan,
  and dirty-development package verification also pass.
- Disposable-project dogfood proved `init`, `status`, the Git boundary,
  proof-required `checkpoint`, the Outcome validator, and the real browser.
  It also caught and closed the false `Working now` state when all tasks were
  complete but outcome proof was still missing.
- No live Steer application loop, microphone path, exceptional Ask dogfood, or
  product-name change is claimed.

## Non-goals

- A marketplace for models, tools, or agent personalities.
- A configurable clone of a coding-agent harness.
- A second ledger, raw-transcript archive, or false shared-memory system.
- Voice-only operation without a typed, inspectable fallback.
- Automatic destructive cleanup, publishing, spending, or external messaging.

## Resume Here

Start with the exceptional Ask row on top of the already-proved local Outcome
card, then run the full dogfood gate. Implement live Steer application only
after the typed flow survives that dogfood. Keep provider routing and execution
in the coding host. Do not begin microphone capture, rename Vidux, or expand
into an IDE until the typed Steer loop is demonstrably useful.
