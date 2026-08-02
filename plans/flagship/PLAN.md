# Vidux flagship convergence plan

**Status:** in progress

**Parent authority:** [`../../PLAN.md`](../../PLAN.md)

This plan defines the future flagship product. It does not change the current
1.2.0 release contract until the ordered gates below are green.

## The decision

Adopt **Pilot Puppy** as the product umbrella and make it the calm local work
conductor. Keep **Vidux** as the existing public repository and durable core
name during the migration:

> State the outcome once. Pilot Puppy keeps the human flow; Vidux keeps the plan
> and proof. Its little driver moves the work. Native Codex, Claude, or Cursor executes it. 90 lets
> you choose the next move from your phone or voice without staring at the
> machinery.

Do not create a new repository, rewrite the Vidux history, or rename the
repository/package in this cycle. The existing Vidux release and links remain
the compatibility base; the successor brand is Pilot Puppy, with any repository
rename deferred until a working successor release proves the migration safe.

The shipping shape is **one installable product with strict internal modules**,
not one fused mega-runtime and not a collection of competing products.

### One product, a friendly internal cast

**Pilot Puppy is the only product and the only name a normal user needs.** It is
the friendly umbrella for the Vidux core, the Chief of Staff briefing, the 90
on-the-go client, and the hidden right-hand driver that plans, delegates, checks
proof, and reports back. It is not a second app, install choice, queue, or
authority. The maintainer/developer entry point is `/pilot-puppy`; `/pilot`
remains a compatibility alias, and the existing `pilot.*` schemas and
environment names remain stable. This is an additive brand/product layer, not
a history rewrite or a second runtime.

The same product may later ship through three thin distribution surfaces:

1. a local skill/CLI for developers who want full custody;
2. optional ChatGPT, Claude, or Cursor wrappers that present Pilot Puppy's typed
   semantic API; and
3. a native iOS/iPad client for the same tailnet-only API.

Those wrappers are Pilot Puppy interfaces, not cloud executors. They never receive source,
credentials, raw transcripts, or a second plan store. A non-technical user can
discover Pilot Puppy through a hosted or marketplace surface without a GitHub or npm
workflow, while the Mac remains the execution and credential boundary.

In the interface, the cast stays plain: Pilot Puppy gives the Chief of Staff
brief, Vidux keeps the durable truth, and 90 asks which useful choice comes
next. The system never requires a user to understand agents, providers, queues,
or implementation modules to get work done.

## Roles (one sentence each)

| Surface | Owns | Must not own |
|---|---|---|
| **Pilot Puppy umbrella** | The single product identity and its human-scale flow across briefing, driving, proof, and choice | a second plan store, raw chat memory, silent provider decisions, user-facing fleet clutter |
| **Chief of Staff brief** | Concise status, material changes, risks, Leo's needed actions, recommendation, and proof/unknowns | execution, provider routing, acceptance, hidden background watching, a second authority |
| **Vidux core** | `PLAN.md`, Outcome / Ask / Steer, proof references, resume, worktree and ownership contracts | provider choice, worker execution, credentials, cloud orchestration |
| **Pilot Puppy driver** | Leo's hidden right-hand driver: plan, split, dispatch, supervise, accept, and fold receipts start-to-finish | a second plan store, raw chat memory, silent provider decisions, user-facing fleet clutter |
| **Host adapter boundary** | The Codex, Claude Code, and direct Cursor invocation and host-native lifecycle contracts | changing the canonical plan without a receipt, exposing credentials to a remote client |
| **90** | Car/on-the-go UX: read concise status, speak one next move, present A/B/C, forward the selected Steer, round-robin ready outcomes | coding, provider routing, background observation, transcript storage, a second driver loop |
| **Ledger** | Append-only bounded activity and handoff evidence | priority, routing, acceptance, or a second authority |
| **Sidekick patterns** | Checkpoint, watchdog, retry, refutation, cold-review behaviors inside Pilot Puppy | a separate runtime or install choice |
| **Swarm patterns** | Task-shape recipes for solo, batched, or parallel bounded work inside Pilot Puppy | a universal cross-provider control plane |
| **MCO** | Optional transport or experiment behind a Pilot Puppy adapter if it proves useful | planner, router, authority, or product identity |
| **Telemetry** | Redacted completion/quality signals | raw prompts, transcripts, secrets, personal paths, or activity theater |
| **Native iOS/iPad app** | A typed remote client over the local semantic API | an execution host, credential vault, or cloud copy of the codebase |

Pilot Puppy is therefore the product. Vidux is its durable core, the Chief of
Staff is its reporting voice, 90 is its steering wheel and dashboard, and the
native hosts are its execution connections. They ship as one umbrella with
contracts that remain testable independently.

### Relatable language

The Pilot Puppy brand promise is **one calm place that tells you what is
happening and what you can do next**. Warmth belongs in the words and the
recovery moments, not in fake progress, mascot clutter, or gamification. Use the
same plain translation everywhere:

| Internal contract | Pilot Puppy-facing language |
|---|---|
| Outcome | What you want |
| Current move | What's happening now |
| Ask | Needs your choice |
| Steer | Change direction |
| Proof | Why Pilot Puppy says it's done |
| Working | Pilot Puppy is on the next move |
| Blocked | Can't continue yet |
| Not delivered | Didn't run |
| Resume | Pick up where you left off |

Pilot Puppy may appear as a small line of personality (for example, “Pilot
Puppy is checking the proof”), but it never becomes mascot clutter or a second
navigation surface. The default screen stays Brief → Now → Change → Proof;
technical detail remains available one tap away for people who want it.

### Chief of Staff briefing

The Chief of Staff is the default reporting behavior, not another agent or
runtime. Every brief answers five questions in plain language: **what changed,
what matters, what is blocked or uncertain, what Leo needs to decide or do, and
what Pilot Puppy recommends next**. It may include one proof link or bounded
receipt, while implementation detail stays collapsed unless Leo asks for it.

When Leo is driving, 90 presents that brief as speech plus at most three
choices. At a desk, the existing Outcome card is the default view and the typed
Chief-of-Staff projection is available in its details. Both surfaces derive
from the same Outcome, PLAN, receipts, and live evidence; neither creates a
second queue, memory, or acceptance authority.

## Why this survives vendor catch-up

The hosts are rapidly absorbing generic orchestration. Cursor now packages MCP,
skills, subagents, rules, and hooks; Codex is a command center for parallel
agents, worktrees, skills, and automations; and Claude is adding subagents,
background tasks, plugins, and long-running sessions. The flagship must not
compete with those execution surfaces.

The durable wedge is the part those vendor surfaces do not share:

1. **Cross-host continuity:** one provider-neutral Outcome and plan survives a
   move between Codex, Claude, and Cursor.
2. **Trustful completion:** a task is not finished because an agent spoke; the
   same outcome receives a terminal proof/acceptance receipt or an explicit
   non-delivery state.
3. **Local custody:** code, credentials, and execution remain on the user's
   Mac; remote clients see typed semantic state, not a cloud mirror of the
   machine.
4. **Human-scale control:** a non-coder sees one current move and one real
   choice, not a model picker, prompt queue, or worker dashboard.
5. **Long-running hygiene:** bounded child plans, ownership, retries, context
   compaction, stale-work detection, and cleanup are observable and reversible.

If dogfood shows that native hosts already deliver these five properties across
all three providers, Vidux should shrink rather than add an agent platform.

## Architecture

```text
                         typed Outcome / Ask / Steer
                                      ^
                                      |
        iPhone / iPad / Codex Voice  90 Drive mode (brief + A/B/C)
                                      |
                       local semantic API (tailnet only)
                                      |
       PLAN.md + proof + ownership  Vidux core inside Pilot Puppy
                                      ^
                                      |
      Pilot Puppy driver (hidden; one lifecycle, one acceptance owner)
                    /             |                \
          Codex adapter     Claude adapter      Cursor adapter
             native host       native host         native host
```

### Core state

Keep the existing provider-neutral Outcome / Ask / Steer schema and pair it
with the separate lifecycle receipt needed to prove:

`planned → dispatched → working → needs-you → proving → finished-with-proof`

Every transition carries an outcome id, plan revision, actor, timestamp, and
proof or honest failure reference. Raw provider messages never become durable
state. One execution leaf owns one worktree; parent progress derives from
terminal child receipts. The public receipt deliberately omits provider/model
fields; private adapters may retain those details in their own bounded evidence.

### Pilot Puppy lifecycle

Pilot Puppy's first flagship gate is one real, boring lifecycle:

`start → freeze packet/context → invoke one native host → resume or Steer →
prove → lead acceptance → fold back to PLAN.md → close or hand off`

The lifecycle is proven through Codex, Claude Code, and the direct Cursor host
adapter. The generic provider worker bridge is not native host parity, and a
Cursor run counts only when the adapter validates one `pilot.host-receipt.v1`.
A projection, model list, or empty provider response is never a run receipt.

### Host adapters

Declare exactly three first-party host paths: Codex, Claude Code, and Cursor.
All three have current native adapters. The direct Cursor path invokes the
current `cursor-agent` CLI once for a frozen task and validates its bounded
receipt; the generic Cursor worker bridge does not satisfy this gate. Each
adapter is a thin translation layer for the host's current native hooks,
subagents, or task APIs. It reports capabilities and proof; it does not move
private credentials into Vidux or invent a shared provider API that the hosts
do not actually implement.

### 90 and mobile

90 consumes the same typed semantic API as the browser cockpit. Its first
multiple-choice loop is deliberately small:

1. read the current outcomes and readiness;
2. speak a concise status and offer at most three meaningful choices;
3. send the chosen Steer to Pilot Puppy;
4. confirm `received`, then later `applied`, `blocked`, or `finished-with-proof`;
5. move to the next ready outcome only after the current handoff is durable.

The native iOS/iPad app is a future client of this API, not a second runtime.
The Mac remains the executor and credential boundary. The app must work over a
tailnet-only connection using Tailscale Serve or an equivalent private route;
Funnel/public exposure is out of scope for the core product.

### Telemetry

Use OpenTelemetry as the vendor-neutral event shape. Langfuse is an optional,
self-hosted sink, not a runtime dependency. The default event contains only
bounded metadata such as outcome id, plan revision, provider/host, model label,
attempt, state, proof status, failure class, time-to-first-progress,
time-to-terminal, interventions, retries, and compactions. It excludes raw
prompts, transcripts, file contents, credentials, absolute paths, and personal
identifiers. Telemetry is off or local-only until a collector health check and a
redaction regression prove otherwise.

## Non-goals (keep the product simple)

- no new universal router or model marketplace;
- no separate Pilot Puppy app, installer, dashboard, or user-facing queue;
- no cloud executor, hosted project database, or credential relay;
- no second plan/queue hidden behind 90, Ledger, MCO, or a mobile app;
- no support matrix beyond Codex, Claude, and Cursor in the first release;
- no background screen reading or raw transcript archive;
- no automatic merge, publish, payment, destructive action, or external message;
- no four-level recursive planning tree without an independent proof/revert
  boundary;
- no repository/package rename, repo split, or history rewrite in this cycle;
  Pilot Puppy branding can ship over the existing Vidux compatibility base.

## Ordered work and gates

- [completed] **F0 — Contract freeze.** Re-read this plan from `origin/main`; pin the
  role map, state machine, public/private boundary, and compatibility aliases.
  Gate: `vidux.lifecycle.v1` schema, fixtures, deterministic validator, and
  negative privacy/transition tests describe the new lifecycle. The contract
  is additive; the existing `vidux.outcome.v1` document remains compatible.
- [completed] **F0.5 — Pilot Puppy umbrella and Chief of Staff brief.** Keep
  Pilot Puppy as the user-facing umbrella over Vidux's durable core. The Chief
  of Staff brief is the default report: what changed, why it matters, what is
  blocked or uncertain, what Leo must do, the recommendation, one proof
  reference, and at most three choices. The desk renderer and public on-the-go
  speech projection already consume the typed `vidux.chief-of-staff.v1`
  contract; the private 90 Drive receipt proves the separate revision-bound
  `vidux.drive.v1` handoff. The private Chief-of-Staff consumer and sanitized
  same-source receipt are recorded in
  [`evidence/2026-08-02-private-chief-of-staff-receipt.md`](evidence/2026-08-02-private-chief-of-staff-receipt.md).
  The desk and 90 render the same bounded payload from one validated Outcome;
  no transport, routing, second queue, or second authority was added. F4 is
  deliberately deferred until a concrete client needs private transport;
  repository/package rename remains deferred.
- [completed] **F1 — Pilot Puppy driver (first real-host gate).** The bounded
  `pilot run` seam preserves `/pilot-puppy`, `/pilot`, and `/leo-flow`
  compatibility. Codex completed one small task on local branch
  `codex/vidux-f1-real-20260801` at `73fcb419`: the provider receipt named
  `f1-real-host`, proof `f1-real-proof` passed, lead acceptance was explicit,
  and the foldback was appended on that evidence branch. Projection-only runs
  still fail closed; F2 owns parity through the other two hosts. The public
  flagship merge now records this gate; the evidence branch remains preserved.
- [completed] **F2 — Host parity contract and direct runtime proof.** Freeze the
  three-host receipt contract and capability probes, then reproduce the same
  bounded task through the other two hosts while recording honest capability
  differences. Gate: no adapter writes outside its assigned worktree; missing
  host, auth, or proof is an explicit blocked/non-delivery result; no lossy
  lowest-common-denominator contract. Codex and Claude Code retain their
  earlier accepted marker receipts. Shared Pilot PR #151 merged at
  `d9ebdbe1`, adding the direct Cursor adapter and its fail-closed parser. A
  fresh run without an explicit binary invoked `cursor-agent` in a clean
  disposable Git worktree, exited `0`, changed exactly
  `cursor-native-marker.txt`, returned proof `cursor-native-default`, and
  passed the marker test. Earlier missing-receipt attempts remain historical
  `not_delivered` evidence; they do not override this current adapter proof.
  A model list, login status, or empty provider response is never parity
  evidence. Lead acceptance and foldback remain the owning plan's job, not the
  host adapter's.
- [completed] **F3 — 90 semantic client.** Public F3a/F3b provide the pure
  revision-bound Drive projection and compare-and-set receipt without host,
  provider, storage, shell, network, or queue behavior. The owner-supplied
  private-consumer half is recorded once in
  [`evidence/2026-08-02-private-90-drive-receipt.md`](evidence/2026-08-02-private-90-drive-receipt.md).
  F3 is complete; F0.5 is now complete through the owner-supplied
  Chief-of-Staff report-surface receipt. F4 is deliberately deferred until a
  concrete on-the-go client needs private transport.
- [deferred] **F4 — Local transport.** Serve the semantic API on loopback and a
  tailnet-only endpoint only after a concrete on-the-go client requires it.
  The transport mechanism is technically feasible, but it is not the next
  product proof: it adds a network admission and privacy surface without
  answering whether a person understands or trusts the existing local Outcome
  card. Resume only with a named 90/iOS/client use case, one exact read/write
  contract, and a local integration receipt that rejects non-tailnet access.
  Until then, keep the canonical PLAN.md-derived source local and do not add a
  listener, router, queue, credential endpoint, or second state source.
- [completed] **F5 — Local telemetry contract (MVP).** Provide an opt-in,
  loopback-only OTLP projection from bounded semantic lifecycle facts. Gate:
  the allowlist/redaction suite rejects prompt, transcript, content, path,
  secret, and credential leakage; a real local collector receives completion
  and failure spans; non-loopback/auth/proxy diversion is rejected; and
  disabled export leaves the product functional.
  **Claim receipt:** public merge `dcf1fa0a` (PR #41; source head
  `4ce6ad15`) adds the real `TelemetryTests.test_real_loopback_collector_receives_completion_and_failure_spans`
  receipt. Focused telemetry is 8/8, the full Python suite is 492/492, the
  hosted required checks are green, and the clean release/public-ready gates
  pass. The contract is caller-driven and default-off: it adds no runtime
  dependency, automatic producer, remote sink, credential path, or relay.
- [ ] **F5b — Optional telemetry sink and runtime producer.** Revisit a
  self-hosted Langfuse adapter and automatic lifecycle emission only when a
  concrete local consumer, bounded credential-free configuration, and a
  separate end-to-end producer receipt exist. Until then, keep the MVP
  contract-only and local; this row must not add a second state source or
  change F0.5/F3/F4 sequencing.
- [ ] **F6 — Native iOS/iPad client.** Build the smallest read/status/Ask/Steer
  client after F3/F4, not before. Gate: it can reconnect, show stale/offline
  state, send one typed Steer, and never needs source or provider credentials.
- [ ] **F7 — Stranger dogfood and release.** Run build, bug-fix, and release
  scenarios with a non-coder; verify current-state comprehension, one real Ask,
  superseding Steer, and trusted proof. Then run the existing package, browser,
  privacy, and exact-release gates. A rename is considered only after this row.

## Five questions we must answer before adding surface area

1. Does cross-host continuity materially beat simply using Codex, Claude, or
   Cursor alone for a non-coder?
2. Can one receipt contract survive the real differences among the three hosts,
   or are we hiding a permanently lossy abstraction?
3. Does a user trust a concise semantic brief when proof is one tap away, or do
   they need code/log detail on the default screen?
4. Is tailnet onboarding low-friction enough for iPhone/iPad use without making
   Vidux a networking product?
5. Do completion and failure metrics change product decisions, or are we merely
   measuring agent activity?

## Evidence to keep current

Keep these primary sources in the research receipt for each implementation row:

- Cursor changelog: plugins, subagents, hooks, and background-agent custody.
- OpenAI Codex app announcement and Codex plugin help: native parallel work,
  worktrees, skills, and packaged workflows.
- Anthropic Claude Code documentation: local host setup and provider boundary.
- Tailscale Serve and iOS installation documentation: tailnet-only local
  access and iPhone/iPad support.
- OpenTelemetry GenAI semantic conventions: provider/model event attributes.
- Langfuse observability and self-hosting documentation: optional local sink
  and masking behavior.

The public plan keeps source names rather than absolute URLs because the
repository's public-ready gate rejects unapproved external hosts. The research
receipt and release notes may carry the reviewed links separately.

## Progress

- 2026-08-01: Froze the additive `vidux.lifecycle.v1` receipt contract. It
  validates ordered state transitions and terminal proof references without
  embedding provider, model, prompt, transcript, credential, or machine-path
  data. F1 now owns the first real Pilot Puppy lifecycle.
- 2026-08-01: Adopted **Pilot Puppy** as the user-facing product umbrella.
  Vidux remains the public repository and durable core during migration; the
  Chief of Staff is the default reporting behavior, 90 is the on-the-go
  multiple-choice client, and `/pilot` plus `pilot.*` remain compatibility
  aliases behind `/pilot-puppy`. Optional hosted wrappers are Pilot Puppy
  interfaces only and do not move execution or credentials off the user's Mac.
- 2026-08-01: Shipped the shared `vidux.chief-of-staff.v1` projection in public
  merge `c37c26c5` (PR #33). It derives one bounded report from the typed
  Outcome/Drive source and an optional redacted plan summary, caps choices at
  three and proof at one, rejects private/implementation detail, and is covered
  by the release allowlist. Desk and private 90 wiring remain the next F0.5/F3
  proof; no transport or second authority was added.
- 2026-08-01: Shipped the optional desk consumer in public merge `2a6b11a9`
  (PR #35). The browser loads a provider-neutral renderer before the main app;
  it only displays a supplied `vidux.chief-of-staff.v1` payload, caps choices
  at three, collapses proof, and fails closed on unsafe or absent input. The
  existing shell stays unchanged when no semantic payload is present. The
  private 90 consumer and the same-source desk/on-the-go round-trip remain
  unproven; F0.5 stays open and F3 remains owner-bound.
- 2026-08-01: Closed F5 for the MVP as the local telemetry contract. The real
  loopback collector, redaction, disabled-export, non-loopback, and proxy
  diversion proof is public; Langfuse/runtime producer work is isolated as F5b
  and remains deferred until a concrete local consumer and end-to-end receipt
  exist.
- 2026-08-01: Added a public same-source Chief-of-Staff projection assertion in
  `browser/tests/unit/chief-of-staff.test.mjs`. One typed brief is normalized
  and rendered by both the desk HTML view and the on-the-go plain-text adapter;
  the focused suite is now 7/7. This strengthens the public half of F0.5 but
  does not claim the private 90 consumer or close the owner-bound receipt gate.
- 2026-08-02: Closed F3's private-consumer half with the owner-supplied
  sanitized Drive receipt. F0.5 remains open for the exact Chief-of-Staff
  brief consumer; F4 stays gated because public Vidux has no durable Outcome
  store.
- 2026-08-02: Closed F0.5 with the owner-supplied private Chief-of-Staff
  consumer and same-source receipt. The private adapter preserves the Outcome
  revision and identity, presents only A/B/C, strips proof locators and
  implementation fields, and matches the public plain-speech projection. The
  canonical source gate is now satisfied; F4 remains deliberately deferred
  because no concrete client needs transport yet. No transport or second
  authority was introduced.
- 2026-08-02: Thermo/Ponytail stop-work audit: the existing browser surface is
  the highest-value reachable proof and is green across desktop, iPad, and
  iPhone. Do not wire an exceptional Ask, live Steer, F4 transport, or F6
  client from a synthetic payload. The next predicate is one canonical local
  `vidux.outcome.v1` projection from the owning plan, shared by desk and 90 at
  one revision; no second store, queue, router, or transport is allowed.
- 2026-08-02: Follow-up focus audit after the canonical source merged: F4 is
  deliberately deferred, not blocked by missing code. Transport is a separate
  networking/security surface and does not validate the core promise. The next
  move is local human dogfood of the existing Outcome/Chief-of-Staff card;
  resume F4 only when a named on-the-go client needs a private connection and
  supplies the exact contract and rejection proof.
- 2026-08-02: Shared Pilot PR #151 merged the smallest direct Cursor host seam.
  It is one bounded `cursor-agent` invocation with a clean worktree, exact
  allowed paths, and one validated `pilot.host-receipt.v1`; it adds no queue,
  router, model selector, credential relay, or acceptance authority. The
  flagship now records the direct runtime proof while keeping the next product
  gate unchanged: dogfood the existing Outcome/Chief-of-Staff card.
