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

- Status: 1.2.0 Outcome-first GUI source; release identity requires an exact
  matching tag and GitHub Release. The historical 1.1.1 release is unchanged.
- Outcome ID: vidux-public
- Outcome Revision: 2
- Outcome Updated At: 2026-08-02T04:57:24Z
- Outcome State: working
- Outcome: keep the minimal public surface — `init`, `status`, `browse`,
  `checkpoint`, `doctor` — with tests, release-package verification, and the
  public-ready gate wired into CI.
- Next: dogfood the existing canonical Outcome card and its proof/state wording
  before adding any new interaction. Ask, live Steer, transport, router,
  queue, and iOS work remain deferred until a real user fork proves they are
  necessary.
- Validation: `npm run verify` (tests + public-ready gate) and
  `npm run release:verify`.

## Outcome Scorecard

| Metric | Current | Target | Proof |
|---|---|---|---|
| Test suites | green | green | `npm test` |
| Package byte-identity | passing | passing | `npm run release:verify` |
| Public-ready gate | passing | passing | `npm run public-ready:grep` |

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
- [blocked] Define and prove flagship convergence only after that same
  canonical Outcome source exists. Do not widen the current 1.2.0 release
  surface while this predicate is false; see
  [`plans/flagship/PLAN.md`](plans/flagship/PLAN.md).
- [pending] Triage issues and PRs after the repository is public.

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
- [2026-08-01] Keep **Vidux** as the public umbrella and converge the durable
  plan/proof kernel, Pilot driver, 90 car client, and three native host
  adapters behind one installable product. A new name was rejected for now:
  Wayline is already used by live software products and active marks.
  Rebranding is deferred until the product earns a successor release; the
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
- 2026-08-02: Prepared the canonical Outcome-source slice locally with focused
  proof and same-revision desk/90 semantic checks. It is not yet a public
  commit or hosted-release receipt. Ask is deferred pending real dogfood.
