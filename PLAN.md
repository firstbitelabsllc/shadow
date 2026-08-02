# Vidux — Plan

This is the repository's own working plan, kept in the same shape `vidux init`
scaffolds. It is planning authority for this repo; proof lives in the gates it
names, not in this prose.

## Purpose

Ship and maintain Vidux as a small, local-first plan/proof/resume layer that
complements native coding agents. It records durable planning authority
(`PLAN.md`), linked proof, and a read-mostly local cockpit — and it never routes
models, schedules work, or transports provider traffic.

## Evidence

- `README.md` — public contract and quick start.
- `CHANGELOG.md` — released scope and current corrective work.
- Test suites under `tests/` and `browser/tests/`; CI in `.github/workflows/`.

## Constraints

- Local-first and read-mostly: no new mutation, shell execution, secret
  access, or remote dispatch endpoint without an explicit threat model and a
  regression gate.
- The steering inbox and coordination claims stay loopback-only, plan-scoped,
  provider-neutral, non-executing, and independently auditable.
- Provider selection, worker dispatch, and evaluation belong to the coding
  host, never to Vidux.

## Operator Brief

- Status: working
- Outcome ID: vidux-public
- Outcome Revision: 4
- Outcome Updated At: 2026-08-02T07:24:56Z
- Outcome State: working
- Outcome: Help a person understand what the work is trying to achieve, what is happening now, and where to verify proof without opening code or agent machinery.
- Next: Run one ordinary four-question comprehension dogfood before adding any new interaction.
- Validation: Run the public tests and release checks, then record one bounded human card-comprehension receipt.
- Evidence: evidence/outcome-card-dogfood.md

## Outcome Scorecard

| Metric | Baseline | Current | Target | Status | Proof |
|---|---|---|---|---|---|
| Test suites | required | green | green | unproven | `npm test` |
| Package byte-identity | required | passing | passing | unproven | `npm run release:verify` |
| Public-ready gate | required | passing | passing | unproven | `npm run public-ready:grep` |
| Card comprehension | not run | not run | four accurate answers | unproven | evidence/outcome-card-dogfood.md |

## Tasks

- [completed] Cut the CLI to the minimal public surface and align docs.
- [completed] Wire CI: tests, release verification, secret scan, public-ready gate.
- [completed] Reduce the root skill and public fleet guidance to the
  plan/proof/resume boundary; remove private material and references to absent
  helpers; add documentation-target and public-data regressions.
- [completed] Ship the first Outcome-first browser slice: one calm Outcome,
  honest state, current move, local change-direction request, and collapsed
  proof/plan details.
- [deferred] Add and dogfood one exceptional Ask against the canonical
  `vidux.outcome.v1` source only after real Outcome-card dogfood shows a
  genuine fork. Do not build an Ask parser, answer flow, second state store,
  or approval queue to prove the concept.
- [blocked] Run one ordinary comprehension dogfood against the corrected
  canonical Outcome card and proof/state wording. Resume only when
  `evidence/outcome-card-dogfood.md` exists with one ordinary human's four
  answers (outcome, now/needed action, next move, and proof availability).
  Keep the current 1.2.0 surface narrow and use
  [`plans/flagship/PLAN.md`](plans/flagship/PLAN.md) for evidence-triggered
  follow-ups; do not build another interaction to manufacture this receipt.
- [in_progress] Clarify the non-executing response path exposed by the first
  dogfood: when local steering is unavailable, tell the person to answer the
  four questions in their host chat. Re-run the same card check after this
  copy-only correction; do not add an Ask, Steer runtime, queue, or transport.
- [deferred] Triage public issues and PRs only when an assigned issue changes
  the current Outcome gate; it is not a second work queue.

## Decision Log

- [2026-07-21] 1.0.0 is a local source contract, not a published release: no
  npm publication, git tag, or GitHub Release is claimed until one exists.
- [2026-07-21] Internal helpers (steering mailbox, coordination claims, config)
  stay invoked by script path.
- [2026-07-29] `checkpoint` is the fifth public command: an optional plan update
  and local-ledger helper, not a second authority or a publication gate.
  Completion requires explicit proof, and Git commit is opt-in.
- [2026-07-29] Vidux remains the durable plan/proof/cleanup kernel. The Outcome
  Console must make that machinery quiet: one current Outcome, one
  exceptional Ask, a Steer that supersedes stale direction, and proof at the
  end. The coding host still owns provider routing and execution.
- [2026-07-29] The first public slice is an interchange schema plus read-only
  validator. It proves bounded state shape and privacy invariants only; GUI,
  persistence, worker control, and a live stop-stale-work loop remain unproved.
- [2026-07-29] Public source carries product authority, not portfolio
  operations. Provider receipts, private repository links, personal paths,
  costs, and session identifiers are rejected from the maintained surface.
- [2026-07-29] The Outcome-first GUI may save a Steer locally, but it must not
  claim delivery or application until a compatible coding host acknowledges
  it.
- [2026-08-01] Keep **Pilot Puppy** as the user-facing product umbrella and
  keep **Vidux** as the public repository and durable plan/proof core. Converge
  the Pilot driver, 90 car client, and three native host adapters behind one
  installable product. A repository/package rename remains deferred; the
  existing CLI, package, history, and links remain valid.
- [2026-08-01] Freeze the additive `vidux.lifecycle.v1` receipt as the
  provider-neutral transition seam. Pilot owns dispatch and acceptance; the
  receipt records ordered state and bounded proof references without provider,
  model, prompt, transcript, credential, or machine-path data.
- [2026-08-02] Thermo/Ponytail stop-work audit: the smallest useful next move
  is one strict, deterministic PLAN.md-to-`vidux.outcome.v1` projection. Keep
  the existing schema, validator, browser proof, and native adapters; do not
  add a second state store, queue, router, transport, synthetic payload, or
  parallel Ask/Steer/F4/iOS work. Downstream rows stay blocked until the
  projection has one revision shared by desk and 90.
- [2026-08-02] The canonical plan-derived Outcome source is now implemented
  and mechanically checked. The existing plan's explicit identity, revision,
  timestamp, state, summary, and current move feed one closed document plus
  the desk/Drive/90 projections; no path, session, provider, or raw text is
  copied. The next move is dogfood, not an Ask runtime.
- [2026-08-02] Thermo/Ponytail focus audit: keep this one source boundary;
  defer Ask, live Steer, voice, provider routing, and rename work until a
  human can use the current Outcome card and name the missing decision.
- [2026-08-02] Mechanical gates remain green, but the human comprehension
  receipt is still absent. Park the dogfood row rather than imply execution;
  resume only when `evidence/outcome-card-dogfood.md` contains the four
  ordinary-human answers. No Ask, voice, routing, rename, or second runtime
  work is opened while that predicate is false.
- [2026-08-02] Product naming call: **Pilot Puppy** is the visible product
  brand and user-facing umbrella. Keep `Vidux`, `vidux.*` schemas, existing
  CLI/package identifiers, repository slug, and compatibility links as the
  stable public namespace until a separately proved migration can preserve
  installs, integrations, and history. Do not perform a global text
  replacement or history rewrite as branding work.
- [2026-08-02] First ordinary card dogfood exposed a real comprehension gap:
  the operator saw `Needs attention` and `Steering unavailable (409)` but did
  not know what response would unblock the check. Record the failed receipt,
  add one host-chat instruction to that unavailable state, and rerun the same
  read-only check. This is copy-only; it does not make Steering live.
- [2026-08-02] Merged the canonical Outcome-source slice as PR #55 at
  `f21fdce5c9bdb74a0bcab8ad6b0340d83cd6e7b0`. Hosted CI, CodeQL, gitleaks,
  public-ready, and Graphite gates passed. The durable next move is card
  dogfood; no new runtime, queue, router, or Ask surface is implied.
- [2026-08-02] The live card gate is data-first: the Operator Brief now uses
  one-line human fields, an explicit Outcome revision, the shipped six-column
  scorecard shape, and a bounded dogfood proof target. A working Outcome with
  no terminal receipt must say that proof is not available yet; it must not
  imply completion. Ask, live Steer, routing, transport, and new UI remain
  deferred until a real operator exposes a missing decision.

## Progress

- 2026-07-21: 1.0.0 cut — minimal CLI surface, consolidated CI, fresh
  changelog, plan reset to the scaffold shape.
- 2026-07-29: Recorded the Outcome Console opportunity, smallest useful GUI,
  competitor evidence, falsification gates, and bounded first dogfood slice.
  No rename or release claim is implied.
- 2026-07-29: Implemented the first local Outcome view in the existing browser:
  one outcome, current move, local Steer, and proof on demand, with projects
  and technical diagnostics moved out of the default surface. Exceptional Ask
  dogfood and live Steer application remain.
- 2026-07-29: Added the `vidux.outcome.v1` schema, synthetic example,
  reference, and deterministic validator as the provider-neutral boundary.
- 2026-07-29: Sanitized the maintained tip and `1.1.1` source package and
  strengthened the public-boundary gate. A release is valid only when its tag
  and GitHub Release resolve to these exact bytes. The historical `v1.1.0` tag
  and repository ancestry remain unchanged under the no-rewrite policy.
- 2026-07-29: Replaced stale host-database, scheduler, private-ledger, and
  nonexistent-helper guidance with the narrow public contract. Vidux owns
  inspectable repository authority; the coding host owns execution.
- 2026-07-29: Prepared 1.2.0 with the Outcome-first desktop/mobile view,
  truthful completed-without-proof state, and local-only Steer wording.
- 2026-08-01: Opened the flagship convergence plan. It makes Pilot the main
  start-to-finish driver, keeps 90 as the on-the-go A/B/C client, and preserves
  Vidux as the provider-neutral durable authority.
- 2026-08-01: Added the lifecycle receipt schema, examples, public reference,
  deterministic validator, focused tests, and release-package requirements.
- 2026-08-02: Re-ranked the flagship and Outcome Console rows behind the one
  canonical Outcome-source gate after a bounded privacy and parser audit.
- 2026-08-02: Prepared and merged the canonical Outcome-source slice with
  focused proof, same-revision desk/90 semantic checks, and green hosted
  gates (PR #55, merge `f21fdce5c9bdb74a0bcab8ad6b0340d83cd6e7b0`). Ask is
  deferred pending real dogfood.
